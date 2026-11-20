#include "dp_model.h"

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *const dp_exts[] = {
    ".bin", ".gen", ".md", ".smd", ".32x", ".sms", ".gg", ".nes", ".fds", ".sfc", ".smc",
    ".gb", ".gbc", ".gba", ".n64", ".z64", ".v64", ".nds", ".pce", ".cue", ".chd", ".iso",
    ".pbp", ".cso", ".gdi", ".cdi", ".zip", ".7z", ".a26", ".a78", ".col", ".vec", ".dsk",
    ".tap", ".tzx", ".adf", ".d64", ".prg", ".lnx", ".ngc", ".ws", ".wsc", ".vb", ".min",
    ".sh", ".st", ".stx", ".j64", ".jag", ".int", ".tv", ".pgm", ".scv", ".xex", ".atr", ".cas",
};

static int dp_has_ext(const char *name, const char *extensions)
{
    const char *dot = strrchr(name, '.');
    if (!dot || dot == name)
        return 0;
    for (size_t i = 0; i < sizeof(dp_exts) / sizeof(dp_exts[0]); i++) {
        if (strcasecmp(dot, dp_exts[i]) == 0)
            return 1;
    }
    size_t length = strlen(dot);
    while (*extensions) {
        size_t token = strcspn(extensions, " \t\r\n");
        if (token == length && strncasecmp(extensions, dot, length) == 0)
            return 1;
        extensions += token;
        extensions += strspn(extensions, " \t\r\n");
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
    if (m) {
        for (int i = 0; i < m->nroms; i++)
            free(m->rom_names[i]);
        free(m->rom_names);
    }
    free(m);
}

static int is_rom(DIR *dir, const char *name, const char *extensions)
{
    struct stat st;
    return name[0] != '.' && dp_has_ext(name, extensions)
        && fstatat(dirfd(dir), name, &st, 0) == 0 && S_ISREG(st.st_mode);
}

static int dp_count_roms(const char *dir, const char *extensions)
{
    DIR *d = opendir(dir);
    if (!d)
        return 0;
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (is_rom(d, e->d_name, extensions))
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

static void system_extensions(FILE *registry, struct dp_system *system)
{
    if (!registry)
        return;
    rewind(registry);
    char line[320];
    while (fgets(line, sizeof(line), registry)) {
        char *tab = strchr(line, '\t');
        if (!tab)
            continue;
        *tab = '\0';
        if (strcmp(line, system->id) == 0) {
            snprintf(system->extensions, sizeof(system->extensions), "%.255s", tab + 1);
            return;
        }
    }
}

static int scan_library(struct dp_model *m, const char *roms_dir, const char *prefix, FILE *registry)
{
    char root[1024];
    if (snprintf(root, sizeof(root), "%s/%s", roms_dir, prefix) >= (int)sizeof(root))
        return -1;
    DIR *d = opendir(root);
    if (!d)
        return -1;
    struct dirent *e;
    while ((e = readdir(d)) != NULL && m->nsys < DP_MAX_SYSTEMS) {
        if (e->d_name[0] == '.' || strlen(e->d_name) >= DP_SYS_ID ||
            strcasecmp(e->d_name, "bios") == 0 || strcasecmp(e->d_name, "roms") == 0)
            continue;
        struct dp_system s = {0};
        snprintf(s.id, sizeof(s.id), "%.23s", e->d_name);
        snprintf(s.folder, sizeof(s.folder), "%.5s%.23s", prefix, e->d_name);
        for (char *p = s.id; *p; p++) {
            if (*p >= 'A' && *p <= 'Z')
                *p = (char)(*p - 'A' + 'a');
        }
        int duplicate = 0;
        for (int i = 0; i < m->nsys; i++)
            if (strcmp(m->systems[i].id, s.id) == 0)
                duplicate = 1;
        if (duplicate)
            continue;
        char path[2048];
        snprintf(path, sizeof(path), "%s/%s", roms_dir, s.folder);
        system_extensions(registry, &s);
        s.games = (unsigned)dp_count_roms(path, s.extensions);
        if (!s.games)
            continue;
        dp_system_name(s.id, s.name, sizeof(s.name));
        m->systems[m->nsys++] = s;
        m->total_games += s.games;
    }
    closedir(d);
    return 0;
}

int dp_model_scan(struct dp_model *m, const char *roms_dir)
{
    m->nsys = 0;
    m->total_games = 0;
    FILE *registry = fopen("/data/emus/extensions.tsv", "r");
    m->roms_ok = scan_library(m, roms_dir, "", registry) == 0;
    if (m->roms_ok)
        scan_library(m, roms_dir, "roms/", registry);
    if (registry)
        fclose(registry);
    if (!m->roms_ok)
        return -1;
    qsort(m->systems, (size_t)m->nsys, sizeof(m->systems[0]), dp_sys_cmp);
    return m->nsys;
}

static int rom_cmp(const void *a, const void *b)
{
    const char *x = *(char *const *)a;
    const char *y = *(char *const *)b;
    int order = strcasecmp(x, y);
    return order != 0 ? order : strcmp(x, y);
}

int dp_model_load_games(struct dp_model *m, const char *roms_dir, int system_index)
{
    for (int i = 0; i < m->nroms; i++)
        free(m->rom_names[i]);
    free(m->rom_names);
    m->rom_names = NULL;
    m->nroms = 0;
    if (system_index < 0 || system_index >= m->nsys)
        return 0;
    char path[2048];
    const struct dp_system *system = &m->systems[system_index];
    int len = snprintf(path, sizeof(path), "%s/%s", roms_dir, system->folder);
    if (len < 0 || (size_t)len >= sizeof(path))
        return -1;
    DIR *d = opendir(path);
    if (!d)
        return -1;

    size_t capacity = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!is_rom(d, e->d_name, system->extensions))
            continue;
        if ((size_t)m->nroms == capacity) {
            size_t next = capacity ? capacity * 2 : 32;
            char **items = realloc(m->rom_names, next * sizeof(*items));
            if (!items)
                break;
            m->rom_names = items;
            capacity = next;
        }
        char *name = strdup(e->d_name);
        if (!name)
            break;
        m->rom_names[m->nroms++] = name;
    }
    closedir(d);
    if (m->nroms > 1)
        qsort(m->rom_names, (size_t)m->nroms, sizeof(*m->rom_names), rom_cmp);
    return m->nroms;
}

int dp_model_load_continue(struct dp_model *m, const char *data_dir)
{
    m->data_ok = access(data_dir, R_OK | W_OK) == 0 ? 1 : 0;
    char path[1024];
    snprintf(path, sizeof(path), "%s/continue.tsv", data_dir);
    m->ncont = 0;
    FILE *f = fopen(path, "r");
    if (!f)
        return 0;

    char line[768];
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
