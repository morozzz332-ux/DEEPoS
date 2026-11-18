#include "dp_model.h"

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

static const char *const dp_exts[] = {
    ".bin", ".gen", ".md", ".smd", ".32x", ".sms", ".gg", ".nes", ".fds", ".sfc", ".smc",
    ".gb", ".gbc", ".gba", ".n64", ".z64", ".v64", ".nds", ".pce", ".cue", ".chd", ".iso",
    ".pbp", ".cso", ".gdi", ".cdi", ".zip", ".7z", ".a26", ".a78", ".col", ".vec", ".dsk",
    ".tap", ".tzx", ".adf", ".d64", ".prg", ".lnx", ".ngc", ".ws", ".wsc", ".vb", ".min",
    ".st", ".stx", ".j64", ".jag", ".int", ".tv", ".pgm", ".scv", ".xex", ".atr", ".cas",
};

static int dp_has_ext(const char *name)
{
    const char *dot = strrchr(name, '.');
    if (!dot || dot == name)
        return 0;
    for (size_t i = 0; i < sizeof(dp_exts) / sizeof(dp_exts[0]); i++) {
        if (strcasecmp(dot, dp_exts[i]) == 0)
            return 1;
    }
    return 0;
}

static const struct {
    const char *id;
    const char *name;
} dp_names[] = {
    { "32x", "Sega 32X" },        { "amiga", "Amiga" },
    { "arcade", "Arcade" },       { "atari2600", "Atari 2600" },
    { "atari7800", "Atari 7800" },{ "atarilynx", "Atari Lynx" },
    { "c64", "Commodore 64" },    { "cps1", "CPS-1" },
    { "cps2", "CPS-2" },          { "cps3", "CPS-3" },
    { "dc", "Dreamcast" },        { "dos", "DOS" },
    { "famicom", "Famicom" },     { "gb", "Game Boy" },
    { "gba", "Game Boy Advance" },{ "gbc", "Game Boy Color" },
    { "gg", "Game Gear" },        { "j2me", "J2ME" },
    { "mame", "MAME" },           { "md", "Mega Drive" },
    { "megadrive", "Mega Drive" },{ "n64", "Nintendo 64" },
    { "nds", "Nintendo DS" },     { "neogeo", "Neo Geo" },
    { "nes", "Nintendo NES" },    { "ngp", "Neo Geo Pocket" },
    { "pce", "PC Engine" },       { "pcengine", "PC Engine" },
    { "ports", "Порты" },         { "psp", "PS Portable" },
    { "psx", "PlayStation" },     { "saturn", "Saturn" },
    { "scv", "Super Cassette" },  { "sfc", "Super Nintendo" },
    { "snes", "Super Nintendo" }, { "sms", "Master System" },
    { "vb", "Virtual Boy" },      { "wsw", "WonderSwan" },
    { "wonderswan", "WonderSwan" },{ "ws", "WonderSwan" },
    { "x68000", "X68000" },       { "zx", "ZX Spectrum" },
    { "scummvm", "ScummVM" },     { "pico8", "PICO-8" },
};

void dp_system_name(const char *id, char *out, size_t out_len)
{
    for (size_t i = 0; i < sizeof(dp_names) / sizeof(dp_names[0]); i++) {
        if (strcasecmp(id, dp_names[i].id) == 0) {
            snprintf(out, out_len, "%s", dp_names[i].name);
            return;
        }
    }
    snprintf(out, out_len, "%s", id);
}

struct dp_model *dp_model_new(void)
{
    return calloc(1, sizeof(struct dp_model));
}

void dp_model_free(struct dp_model *m)
{
    free(m);
}

static int dp_count_roms(const char *dir)
{
    DIR *d = opendir(dir);
    if (!d)
        return 0;
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] == '.')
            continue;
        char path[2048];
        /* Bounded widths keep -Wformat-truncation (fortify) quiet and cap the
         * path well below PATH_MAX; deeper trees simply do not appear in scans. */
        snprintf(path, sizeof(path), "%.1000s/%.200s", dir, e->d_name);
        struct stat st;
        if (stat(path, &st) != 0 || !S_ISREG(st.st_mode))
            continue;
        if (dp_has_ext(e->d_name))
            n++;
    }
    closedir(d);
    return n;
}

static int dp_sys_cmp(const void *a, const void *b)
{
    const struct dp_system *x = a, *y = b;
    if (x->games != y->games)
        return x->games < y->games ? 1 : -1;
    return strcmp(x->id, y->id);
}

int dp_model_scan(struct dp_model *m, const char *roms_dir)
{
    DIR *d = opendir(roms_dir);
    if (!d)
        return -1;

    m->nsys = 0;
    m->total_games = 0;

    struct dirent *e;
    while ((e = readdir(d)) != NULL && m->nsys < DP_MAX_SYSTEMS) {
        if (e->d_name[0] == '.')
            continue;
        char path[2048];
        snprintf(path, sizeof(path), "%.1000s/%.200s", roms_dir, e->d_name);
        struct stat st;
        if (stat(path, &st) != 0 || !S_ISDIR(st.st_mode))
            continue;
        int games = dp_count_roms(path);
        if (games <= 0)
            continue;
        struct dp_system *s = &m->systems[m->nsys++];
        snprintf(s->id, sizeof(s->id), "%.23s", e->d_name);
        for (char *p = s->id; *p; p++) {
            if (*p >= 'A' && *p <= 'Z')
                *p = (char)(*p - 'A' + 'a');
        }
        dp_system_name(s->id, s->name, sizeof(s->name));
        s->games = (unsigned)games;
        m->total_games += (unsigned)games;
    }
    closedir(d);

    qsort(m->systems, (size_t)m->nsys, sizeof(m->systems[0]), dp_sys_cmp);
    return m->nsys;
}

int dp_model_load_continue(struct dp_model *m, const char *data_dir)
{
    char path[1024];
    snprintf(path, sizeof(path), "%s/continue.tsv", data_dir);
    FILE *f = fopen(path, "r");
    if (!f)
        return 0;

    char line[512];
    m->ncont = 0;
    while (fgets(line, sizeof(line), f) && m->ncont < DP_MAX_CONTINUE) {
        size_t len = strlen(line);
        while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';
        if (!len || line[0] == '#')
            continue;
        char *fields[7] = { 0 };
        int nf = 0;
        char *p = line;
        fields[nf++] = p;
        for (; *p && nf < 7; p++) {
            if (*p == '\t') {
                *p = '\0';
                fields[nf++] = p + 1;
            }
        }
        if (nf < 2)
            continue;
        struct dp_continue_item *it = &m->cont[m->ncont];
        snprintf(it->title, sizeof(it->title), "%s", fields[0]);
        snprintf(it->system, sizeof(it->system), "%s", fields[1]);
        if (nf > 2 && fields[2])
            snprintf(it->meta, sizeof(it->meta), "%s", fields[2]);
        it->slot = (nf > 3 && fields[3]) ? atoi(fields[3]) : -1;
        it->has_save = (nf > 4 && fields[4]) ? atoi(fields[4]) : (it->slot >= 0);
        if (nf > 5 && fields[5])
            snprintf(it->sys_id, sizeof(it->sys_id), "%s", fields[5]);
        if (nf > 6 && fields[6])
            snprintf(it->rom, sizeof(it->rom), "%s", fields[6]);
        m->ncont++;
    }
    fclose(f);
    return m->ncont;
}
