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
            free(m->roms[i].name);
        free(m->roms);
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

static int is_reserved_folder(const char *name)
{
    /* Folders the launcher owns itself. A stray .sh in /storage/report used to
     * show up as a "REPORT" console full of helper scripts. */
    static const char *const reserved[] = {
        "bios", "roms", "modules", "report", "portmaster", "saves", "lost+found",
    };
    for (size_t i = 0; i < sizeof(reserved) / sizeof(reserved[0]); i++)
        if (strcasecmp(name, reserved[i]) == 0)
            return 1;
    return 0;
}

static int scan_library(struct dp_model *m, const char *roms_dir, const char *prefix,
                        FILE *registry, enum dp_rom_source source)
{
    char root[1024];
    if (snprintf(root, sizeof(root), "%s/%s", roms_dir, prefix) >= (int)sizeof(root))
        return -1;
    DIR *d = opendir(root);
    if (!d)
        return -1;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] == '.' || strlen(e->d_name) >= DP_SYS_ID ||
            is_reserved_folder(e->d_name))
            continue;
        struct dp_system s = {0};
        char *folder = s.folders[source - 1];
        snprintf(s.id, sizeof(s.id), "%.23s", e->d_name);
        snprintf(folder, sizeof(s.folders[0]), "%.5s%.23s", prefix, e->d_name);
        for (char *p = s.id; *p; p++) {
            if (*p >= 'A' && *p <= 'Z')
                *p = (char)(*p - 'A' + 'a');
        }
        int existing = 0;
        while (existing < m->nsys && strcmp(m->systems[existing].id, s.id) != 0)
            existing++;
        if ((existing == m->nsys && m->nsys >= DP_MAX_SYSTEMS) ||
            (existing < m->nsys && m->systems[existing].folders[source - 1][0]))
            continue;
        char path[2048];
        snprintf(path, sizeof(path), "%s/%s", roms_dir, folder);
        system_extensions(registry, &s);
        s.games = (unsigned)dp_count_roms(path, s.extensions);
        if (!s.games)
            continue;
        if (existing == m->nsys) {
            dp_system_name(s.id, s.name, sizeof(s.name));
            s.tf2_games = source == DP_ROM_TF2 ? s.games : 0;
            m->systems[m->nsys++] = s;
        } else {
            struct dp_system *target = &m->systems[existing];
            snprintf(target->folders[source - 1], sizeof(target->folders[0]), "%s", folder);
            target->games += s.games;
            if (source == DP_ROM_TF2)
                target->tf2_games = s.games;
        }
        m->total_games += s.games;
    }
    closedir(d);
    return 0;
}

int dp_model_scan(struct dp_model *m, const char *roms_dir)
{
    m->nsys = 0;
    m->total_games = 0;
    /* DP_EXTENSIONS lets the test harness point the scanner at a throw-away
     * registry instead of the one the image ships in /data/emus. */
    const char *registry_path = getenv("DP_EXTENSIONS");
    FILE *registry = fopen(registry_path ? registry_path : "/data/emus/extensions.tsv",
                           "r");
    if (getenv("DP_DEBUG_SCAN"))
        fprintf(stderr, "scan: root=%s registry=%s tf2=%s\n", roms_dir,
                registry ? (registry_path ? registry_path : "/data/emus/extensions.tsv")
                         : "(none)",
                m->tf2_root ? m->tf2_root : "(none)");
    m->roms_ok = scan_library(m, roms_dir, "", registry, DP_ROM_TF1) == 0;
    if (m->roms_ok)
        scan_library(m, roms_dir, "roms/", registry, DP_ROM_TF1);
    m->tf2_ok = m->tf2_root && scan_library(m, m->tf2_root, "", registry, DP_ROM_TF2) == 0;
    if (m->tf2_ok)
        scan_library(m, m->tf2_root, "roms/", registry, DP_ROM_TF2);
    if (registry)
        fclose(registry);
    if (!m->roms_ok && !m->tf2_ok)
        return -1;
    qsort(m->systems, (size_t)m->nsys, sizeof(m->systems[0]), dp_sys_cmp);
    return m->nsys;
}

static int rom_cmp(const void *a, const void *b)
{
    const struct dp_rom_item *x = a, *y = b;
    int order = strcasecmp(x->name, y->name);
    if (!order)
        order = strcmp(x->name, y->name);
    return order ? order : (int)x->source - (int)y->source;
}

static void load_games(struct dp_model *m, const char *root, const struct dp_system *system,
                       enum dp_rom_source source, size_t *capacity)
{
    char path[2048];
    const char *folder = system->folders[source - 1];
    if (!root || !*folder)
        return;
    int len = snprintf(path, sizeof(path), "%s/%s", root, folder);
    if (len < 0 || (size_t)len >= sizeof(path))
        return;
    DIR *d = opendir(path);
    if (!d)
        return;

    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (!is_rom(d, e->d_name, system->extensions))
            continue;
        if ((size_t)m->nroms == *capacity) {
            size_t next = *capacity ? *capacity * 2 : 32;
            struct dp_rom_item *items = realloc(m->roms, next * sizeof(*items));
            if (!items)
                break;
            m->roms = items;
            *capacity = next;
        }
        char *name = strdup(e->d_name);
        if (!name)
            break;
        m->roms[m->nroms++] = (struct dp_rom_item){name, source};
    }
    closedir(d);
}

int dp_model_load_games(struct dp_model *m, const char *roms_dir, int system_index)
{
    for (int i = 0; i < m->nroms; i++)
        free(m->roms[i].name);
    free(m->roms);
    m->roms = NULL;
    m->nroms = 0;
    if (system_index < 0 || system_index >= m->nsys)
        return 0;
    const struct dp_system *system = &m->systems[system_index];
    size_t capacity = 0;
    load_games(m, roms_dir, system, DP_ROM_TF1, &capacity);
    load_games(m, m->tf2_root, system, DP_ROM_TF2, &capacity);
    if (m->nroms > 1)
        qsort(m->roms, (size_t)m->nroms, sizeof(*m->roms), rom_cmp);
    return m->nroms;
}

enum dp_rom_source dp_model_rom_path(const struct dp_model *m, const char *roms_dir,
                                     const char *id, const char *rom, enum dp_rom_source source,
                                     char *path, size_t size)
{
    const struct dp_system *system = NULL;
    for (int i = 0; i < m->nsys; i++)
        if (!strcmp(m->systems[i].id, id)) {
            system = &m->systems[i];
            break;
        }
    for (enum dp_rom_source card = DP_ROM_TF1; card <= DP_ROM_TF2; card++) {
        if (source != DP_ROM_AUTO && card != source)
            continue;
        const char *root = card == DP_ROM_TF2 ? m->tf2_root : roms_dir;
        const char *folder = system ? system->folders[card - 1] : id;
        if (!root || !*folder)
            continue;
        int len = snprintf(path, size, "%s/%s/%s", root, folder, rom);
        struct stat file;
        if (len >= 0 && (size_t)len < size && stat(path, &file) == 0 && S_ISREG(file.st_mode))
            return card;
    }
    return DP_ROM_AUTO;
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
        char *fields[8] = { 0 };
        int nf = 0;
        char *p = line;
        fields[nf++] = p;
        for (; *p && nf < 8; p++) {
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
        it->source = nf > 7 && !strcmp(fields[7], "tf2") ? DP_ROM_TF2 :
                     nf > 7 && !strcmp(fields[7], "tf1") ? DP_ROM_TF1 : DP_ROM_AUTO;
        m->ncont++;
    }
    fclose(f);
    return m->ncont;
}
