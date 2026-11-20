#include "dp_theme.h"

#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

struct dp_theme dp_theme_current;

static const struct {
    const char *id, *label;
    enum dp_layout layout;
    unsigned bg, panel, text, accent;
} stock[] = {
    { "terminal", "Терминал", DP_LAYOUT_GRID, 0, 0, 0, 0 },
    { "zone", "Зона", DP_LAYOUT_SPLIT, 0x181c14, 0x293021, 0xe0e5cf, 0xefb74d },
    { "garage", "Ночной гараж", DP_LAYOUT_SHELF, 0x0b101c, 0x1c2435, 0xf0f5ff, 0x54ddfc },
    { "signal", "Несущий сигнал", DP_LAYOUT_SPLIT, 0x171819, 0x26292c, 0xf4eee7, 0xffa350 },
    { "outpost", "Последний рубеж", DP_LAYOUT_GRID, 0x1b1014, 0x351921, 0xffeee8, 0xff8577 },
    { "orbit", "Орбитальный сканер", DP_LAYOUT_SPLIT, 0x0b141e, 0x152c43, 0xe4f7ff, 0xffbc6a },
    { "logbook", "Бортовой журнал", DP_LAYOUT_LIST, 0x0e0e0e, 0x222222, 0xffeed5, 0xf0ce96 },
    { "metro", "Подземная линия", DP_LAYOUT_SHELF, 0x151412, 0x282421, 0xece4d2, 0xe9a97d },
    { "guild", "Гильдия", DP_LAYOUT_SPLIT, 0x1c1311, 0x372622, 0xf4dec4, 0xf68b7e },
    { "atlas", "Атлас", DP_LAYOUT_GRID, 0xe5d5ae, 0xf6e8c8, 0x1a2b40, 0x653620 },
    { "village", "Деревенский журнал", DP_LAYOUT_LIST, 0xf1dfac, 0xffefc4, 0x272a17, 0x425d2d },
    { "arcade", "Зал автоматов", DP_LAYOUT_GRID, 0x161737, 0x2f2d55, 0xfff1e6, 0xff978c },
};

static unsigned mix(unsigned a, unsigned b, unsigned percent)
{
    unsigned result = 0;
    for (unsigned shift = 0; shift < 24; shift += 8)
        result |= ((((a >> shift) & 255) * (100 - percent) + ((b >> shift) & 255) * percent)
                   / 100) << shift;
    return result;
}

static struct dp_theme make_theme(enum dp_layout layout, unsigned bg, unsigned panel,
                                  unsigned fg, unsigned accent)
{
    const unsigned rgb[] = {
        bg, panel, mix(panel, fg, 9), mix(panel, fg, 28), fg,
        mix(fg, panel, 15), mix(fg, panel, 27), accent, mix(panel, accent, 20), fg, accent,
    };
    struct dp_theme theme = { .layout = layout };
    for (int i = 0; i < DP_COLOR_COUNT; i++)
        theme.colors[i] = dp565((int)(rgb[i] >> 16), (int)((rgb[i] >> 8) & 255), (int)(rgb[i] & 255));
    return theme;
}

static struct dp_theme terminal(void)
{
    return (struct dp_theme){ .layout = DP_LAYOUT_GRID,
        .colors = { DP_COL_BG, DP_COL_PANEL, DP_COL_PANEL2, DP_COL_LINE, DP_COL_FG,
                    DP_COL_FG2, DP_COL_FG3, DP_COL_ACC, DP_COL_SEL, DP_COL_WARN, DP_COL_BAD } };
}

int dp_theme_id_valid(const char *id)
{
    if (!id || !*id || strlen(id) >= DP_THEME_ID)
        return 0;
    if (!strncmp(id, "user.", 5))
        id += 5;
    return *id && strspn(id, "abcdefghijklmnopqrstuvwxyz0123456789-_") == strlen(id);
}

static int open_user_dir(const char *roms)
{
    int root = open(roms, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (root < 0)
        return -1;
    int dir = openat(root, "themes", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    close(root);
    return dir;
}

static int luma(unsigned rgb)
{
    return (int)((((rgb >> 16) & 255) * 2126 + ((rgb >> 8) & 255) * 7152 +
                  (rgb & 255) * 722) / 10000);
}

static int load_user(int dir, const char *name, struct dp_theme *out)
{
    char file[DP_THEME_ID + 6];
    snprintf(file, sizeof(file), "%s.theme", name);
    int fd = openat(dir, file, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
        return 0;
    const int limit = 1024;
    struct stat st;
    char buf[1025];
    ssize_t n = -1;
    if (fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_size > 0 && st.st_size <= limit)
        n = read(fd, buf, sizeof(buf));
    close(fd);
    if (n <= 0 || n > limit || n != st.st_size || memchr(buf, '\0', (size_t)n))
        return 0;
    buf[n] = '\0';

    static const char *const fields[] = { "format", "layout", "background", "panel", "text", "accent" };
    static const char *const layouts[] = { "grid", "split", "shelf", "list" };
    unsigned values[6] = { 0 }, seen = 0;
    char *state = NULL;
    for (char *line = strtok_r(buf, "\r\n", &state); line; line = strtok_r(NULL, "\r\n", &state)) {
        line += strspn(line, " \t");
        if (!*line || *line == '#')
            continue;
        char *eq = strchr(line, '=');
        if (!eq)
            return 0;
        char *key_end = eq;
        while (key_end > line && (key_end[-1] == ' ' || key_end[-1] == '\t'))
            key_end--;
        *key_end = '\0';
        char *val = eq + 1 + strspn(eq + 1, " \t");
        val[strcspn(val, " \t")] = '\0';
        unsigned key = 0;
        while (key < 6 && strcmp(line, fields[key]) != 0)
            key++;
        if (key == 6 || (seen & (1u << key)))
            return 0;
        if (key == 0 && strcmp(val, "1") != 0)
            return 0;
        if (key == 1) {
            while (values[key] < 4 && strcmp(val, layouts[values[key]]) != 0)
                values[key]++;
            if (values[key] == 4)
                return 0;
        }
        if (key >= 2) {
            if (strlen(val) != 6 || strspn(val, "0123456789abcdefABCDEF") != 6)
                return 0;
            values[key] = (unsigned)strtoul(val, NULL, 16);
        }
        seen |= 1u << key;
    }
    if (seen != 63 || abs(luma(values[4]) - luma(values[2])) < 110 ||
        abs(luma(values[4]) - luma(values[3])) < 110 ||
        abs(luma(values[5]) - luma(values[3])) < 80)
        return 0;
    *out = make_theme(values[1], values[2], values[3], values[4], values[5]);
    return 1;
}

int dp_theme_load(const char *roms, const char *id, struct dp_theme *out)
{
    *out = terminal();
    if (!dp_theme_id_valid(id))
        return 0;
    if (!strcmp(id, "terminal"))
        return 1;
    for (unsigned i = 1; i < sizeof(stock) / sizeof(stock[0]); i++) {
        if (strcmp(id, stock[i].id) == 0) {
            *out = make_theme(stock[i].layout, stock[i].bg, stock[i].panel, stock[i].text, stock[i].accent);
            return 1;
        }
    }
    if (strncmp(id, "user.", 5))
        return 0;
    int dir = open_user_dir(roms);
    if (dir < 0)
        return 0;
    int valid = load_user(dir, id + 5, out);
    close(dir);
    return valid;
}

static int order_entry(const void *a, const void *b)
{
    const struct dp_theme_entry *first = a, *second = b;
    return strcmp(first->id, second->id);
}

int dp_theme_list(const char *roms, struct dp_theme_entry entries[DP_THEME_MAX])
{
    const int base = (int)(sizeof(stock) / sizeof(stock[0]));
    for (int i = 0; i < base; i++) {
        snprintf(entries[i].id, sizeof(entries[i].id), "%s", stock[i].id);
        entries[i].label = stock[i].label;
    }
    int dir = open_user_dir(roms);
    if (dir < 0)
        return base;
    DIR *d = fdopendir(dir);
    if (!d) {
        close(dir);
        return base;
    }
    int count = base;
    struct dirent *ent;
    for (int scanned = 0; scanned < 256 && count < DP_THEME_MAX && (ent = readdir(d)); scanned++) {
        size_t n = strlen(ent->d_name);
        if (n <= 6 || n >= DP_THEME_ID + 1 || strcmp(ent->d_name + n - 6, ".theme"))
            continue;
        struct dp_theme_entry *entry = &entries[count];
        snprintf(entry->id, sizeof(entry->id), "user.%.*s", (int)(n - 6), ent->d_name);
        struct dp_theme preview;
        if (!dp_theme_id_valid(entry->id) || !load_user(dir, entry->id + 5, &preview))
            continue;
        entry->label = NULL;
        count++;
    }
    closedir(d);
    qsort(entries + base, (size_t)(count - base), sizeof(*entries), order_entry);
    return count;
}

const char *dp_theme_label(const char *id)
{
    for (unsigned i = 0; i < sizeof(stock) / sizeof(stock[0]); i++) {
        if (strcmp(stock[i].id, id) == 0)
            return stock[i].label;
    }
    return strncmp(id, "user.", 5) == 0 ? id + 5 : stock[0].label;
}
