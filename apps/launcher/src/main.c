/* DEEPoS launcher - entry point: screen rendering, navigation, game launch. */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
#include "dp_display.h"
#include "dp_input.h"
#include "dp_config.h"
#include "dp_modc.h"
#include "dp_model.h"
#include "dp_sound.h"
#include "dp_theme.h"
#include "dp_ui.h"

static void usage(void)
{
    puts("usage: launcher [options]\n"
         "  --roms DIR        ROM library root (default /storage)\n"
         "  --data DIR        DEEPoS data dir (default /data)\n"
         "  --screen NAME     continue|systems|games|settings|modules|files|info\n"
         "  --out FILE.ppm    write the rendered frame (P6)\n"
         "  --boot-splash     draw the startup logo once and exit\n"
         "  --system N        system index for the games screen\n"
         "  --battery N       battery percentage 0..100\n"
         "  --charging        draw the charging mark\n"
         "  --clock HH:MM     status-bar time\n"
         "  --rom-used MB     used megabytes on the ROM partition\n"
         "  --rom-total MB    total megabytes on the ROM partition\n"
         "  --keys LIST       apply synthetic keys (comma separated, for tests)\n"
         "  --print-state     print navigation state instead of rendering\n"
         "  --list            list available screens\n"
         "  --config PATH     settings file (default /data/config/settings.toml)\n"
         "  --set KEY=VAL     change one setting and save it (brightness/volume/profile)\n"
         "  --print-config    print the effective settings and exit\n"
         "  --apply           write settings to sysfs/profile file\n"
         "  --sysfs PREFIX    sysfs root for --apply (tests, default empty)\n"
         "  --selftest        print the device environment and exit\n"
        "  --list-roms       list detected ROM systems with game counts\n");
}

#define TABS_COUNT 6
#define DEFAULT_EMULATORS "/data/emulators.toml"
#define BUILTIN_EMULATORS "/usr/share/deepos/emulators.toml"
#define IMPORTED_EMULATORS "/data/emus/systems.toml"

struct dp_nav {
    int tab;        /* 0 continue, 1 games, 2 settings, 3 modules, 4 files, 5 info */
    int level;      /* games tab: 0 = system list, 1 = game list */
    int sel;
    int system;
    int launch;     /* set when the user asked to start a game */
    char lsys[32];
    char lrom[DP_ROM_NAME];
    int lslot;
    int settings_edit; /* card index + 1, applied after the key */
    int volume_delta;
    struct { int tab, sel; } back[2];
    int nback;
    int module_action;
    pid_t backup_pid;
    char notice[128];  /* one-shot message drawn above the hint bar */
};

static int tab_screen(const struct dp_nav *nav)
{
    switch (nav->tab) {
    case 0:
        return DP_SCR_CONTINUE;
    case 1:
        return nav->level == 0 ? DP_SCR_SYSTEMS : DP_SCR_GAMES;
    case 2:
        return DP_SCR_SETTINGS;
    case 3:
        return DP_SCR_MODULES;
    case 4:
        return DP_SCR_FILES;
    default:
        return DP_SCR_INFO;
    }
}

static int tab_from_screen(int scr)
{
    switch (scr) {
    case DP_SCR_CONTINUE:
        return 0;
    case DP_SCR_SYSTEMS:
    case DP_SCR_GAMES:
        return 1;
    case DP_SCR_SETTINGS:
        return 2;
    case DP_SCR_MODULES:
        return 3;
    case DP_SCR_FILES:
        return 4;
    default:
        return 5;
    }
}

static int row_count(const struct dp_model *m, const struct dp_nav *nav)
{
    int scr = tab_screen(nav);
    if (scr == DP_SCR_CONTINUE)
        return m->ncont;
    if (scr == DP_SCR_SYSTEMS)
        return m->nsys;
    if (scr == DP_SCR_GAMES)
        return m->nroms;
    if (scr == DP_SCR_SETTINGS)
        return 12;
    if (scr == DP_SCR_MODULES)
        return m->nmods;
    if (scr == DP_SCR_FILES)
        return 3;
    return 0;
}

/* Settings cards that own a value: brightness, volume and the cpu profile.
 * A press cycles the value, writes settings.toml and applies it right away. */
static int settings_edit_card(struct dp_nav *nav, struct dp_model *m, int card, const char *config_path,
                              const char *sysfs_prefix, const char *data_dir)
{
    struct dp_config cfg;
    dp_config_init(&cfg);
    dp_config_load(&cfg, config_path);
    cfg.brightness = m->cfg_brightness;
    cfg.volume = m->cfg_volume;
    snprintf(cfg.profile, sizeof(cfg.profile), "%s",
             m->cfg_profile[0] ? m->cfg_profile : "auto");

    static const int steps[] = { 20, 40, 60, 80, 100 };
    const int nsteps = (int)(sizeof(steps) / sizeof(steps[0]));
    static const char *profiles[] = { "eco", "balanced", "max" };
    const int nprofiles = 3;
    int changed = 0;

    if (card == 2) { /* display */
        int cur = cfg.brightness;
        int next = steps[0];
        for (int i = 0; i < nsteps; i++)
            if (cur >= steps[i])
                next = steps[(i + 1) % nsteps];
        cfg.brightness = next;
        changed = 1;
    } else if (card == 3) { /* sound */
        int cur = cfg.volume;
        int next = steps[0];
        for (int i = 0; i < nsteps; i++)
            if (cur >= steps[i])
                next = steps[(i + 1) % nsteps];
        if (nav->volume_delta) {
            next = (cur > 0 ? cur : 50) + nav->volume_delta;
            if (next > 100)
                next = 100;
            if (next < 1)
                next = 1;
        }
        cfg.volume = next;
        changed = 1;
    } else if (card == 5) { /* power */
        int idx = 0;
        for (int i = 0; i < nprofiles; i++)
            if (strcmp(cfg.profile, profiles[i]) == 0)
                idx = i;
        snprintf(cfg.profile, sizeof(cfg.profile), "%s", profiles[(idx + 1) % nprofiles]);
        changed = 1;
    }
    if (!changed)
        return 0;

    char profile_path[512];
    snprintf(profile_path, sizeof(profile_path), "%s/cpu-profile", data_dir);
    if (dp_config_save(&cfg, config_path) != 0) {
        snprintf(nav->notice, sizeof(nav->notice), "Настройки не сохранены: проверьте DATA");
        return 1;
    }
    int applied;
    if (card == 2)
        applied = dp_config_apply_brightness(sysfs_prefix, cfg.brightness);
    else if (card == 3)
        applied = dp_config_apply_volume(sysfs_prefix, cfg.volume);
    else {
        dp_config_write_profile(profile_path, cfg.profile);
        applied = dp_config_apply_cpu(sysfs_prefix, cfg.profile);
    }
    if (!applied)
        snprintf(nav->notice, sizeof(nav->notice), "Сохранено. Устройство не применило значение");
    m->cfg_brightness = cfg.brightness;
    m->cfg_volume = cfg.volume;
    snprintf(m->cfg_profile, sizeof(m->cfg_profile), "%s", cfg.profile);
    return 1;
}

static int apply_selected_setting(struct dp_nav *nav, struct dp_model *m,
                                  const char *config, const char *sysfs, const char *data)
{
    if (!nav->settings_edit)
        return 0;
    int changed = settings_edit_card(nav, m, nav->settings_edit - 1, config, sysfs, data);
    nav->settings_edit = 0;
    nav->volume_delta = 0;
    return changed;
}

/* Returns 1 when the launcher should quit. */
static void nav_notice(struct dp_nav *nav, const char *message)
{
    snprintf(nav->notice, sizeof(nav->notice), "%s", message ? message : "");
}

static void nav_tab(struct dp_nav *nav, int tab)
{
    nav->tab = (tab + TABS_COUNT) % TABS_COUNT;
    nav->level = 0;
    nav->sel = 0;
    nav->nback = 0;
}

static void nav_shortcut(struct dp_nav *nav, int tab)
{
    if (nav->nback == 2)
        nav->nback = 0;
    nav->back[nav->nback].tab = nav->tab;
    nav->back[nav->nback++].sel = nav->sel;
    nav->tab = tab;
    nav->level = 0;
    nav->sel = 0;
}

static void nav_launch(struct dp_nav *nav, const char *system, const char *rom, int slot)
{
    snprintf(nav->lsys, sizeof(nav->lsys), "%s", system);
    snprintf(nav->lrom, sizeof(nav->lrom), "%s", rom);
    nav->lslot = slot;
    nav->launch = 1;
}

/* 2 = two-column systems grid, 3 = settings cards, 1 = plain list. */
static int nav_grid_cols(int scr)
{
    if (scr == DP_SCR_SYSTEMS)
        return 2;
    if (scr == DP_SCR_SETTINGS)
        return 3;
    return 1;
}

static void nav_clamp(struct dp_nav *nav, struct dp_model *m)
{
    int rows = row_count(m, nav);
    if (rows <= 0) {
        nav->sel = 0;
        return;
    }
    if (nav->sel < 0)
        nav->sel = 0;
    if (nav->sel >= rows)
        nav->sel = rows - 1;
}

/* Left/right inside the games list walks the neighbouring system. */
static void nav_switch_system(struct dp_nav *nav, struct dp_model *m, const char *roms, int dir)
{
    if (m->nsys <= 0)
        return;
    int sys = (nav->system + dir + m->nsys) % m->nsys;
    if (dp_model_load_games(m, roms, sys) == 0) {
        nav->system = sys;
        nav->sel = 0;
    }
}

static int nav_key(struct dp_nav *nav, struct dp_model *m, const char *roms, enum dp_key key)
{
    int rows = row_count(m, nav);
    int scr = tab_screen(nav);
    int cols = nav_grid_cols(scr);

    if (m->input_test && key != DP_KEY_QUIT) {
        if (key == DP_KEY_B && strcmp(m->si.last_key, "b") == 0) {
            m->input_test = 0;
        } else {
            snprintf(m->si.last_key, sizeof(m->si.last_key), "%s", dp_key_name(key));
            return 0;
        }
    }

    switch (key) {
    case DP_KEY_QUIT:
        return 1;
    case DP_KEY_L1:
    case DP_KEY_L2:
        nav_tab(nav, nav->tab - 1);
        break;
    case DP_KEY_R1:
    case DP_KEY_R2:
        nav_tab(nav, nav->tab + 1);
        break;
    case DP_KEY_VOL_UP:
    case DP_KEY_VOL_DOWN:
        nav->settings_edit = 4;
        nav->volume_delta = key == DP_KEY_VOL_UP ? 5 : -5;
        break;
    case DP_KEY_FN:
    case DP_KEY_SELECT:
        if (scr != DP_SCR_INFO)
            nav_tab(nav, 5);
        break;
    case DP_KEY_Y:
        if (scr == DP_SCR_GAMES) {
            nav->level = 0;
            nav->sel = nav->system;
        }
        break;
    case DP_KEY_LEFT:
    case DP_KEY_RIGHT: {
        int dir = key == DP_KEY_RIGHT ? 1 : -1;
        if (scr == DP_SCR_GAMES) {
            nav_switch_system(nav, m, roms, dir);
        } else if (cols > 1) {
            int next = nav->sel + dir;
            if (next >= 0 && next < rows && next / cols == nav->sel / cols)
                nav->sel = next;
        } else {
            nav_tab(nav, nav->tab + dir);
        }
        break;
    }
    case DP_KEY_UP:
    case DP_KEY_DOWN: {
        int dir = key == DP_KEY_DOWN ? 1 : -1;
        if (cols > 1) {
            int next = nav->sel + dir * cols;
            if (dir > 0 && next >= rows && rows > 0 && (rows - 1) / cols > nav->sel / cols)
                next = rows - 1;
            if (next >= 0 && next < rows)
                nav->sel = next;
        } else if (rows > 0) {
            int next = nav->sel + dir;
            if (next < 0)
                next = 0;
            if (next >= rows)
                next = rows - 1;
            nav->sel = next;
        }
        break;
    }
    case DP_KEY_A:
    case DP_KEY_START:
    case DP_KEY_X:
        if (key == DP_KEY_X && scr != DP_SCR_CONTINUE)
            break;
        if (scr == DP_SCR_SYSTEMS && m->nsys > 0) {
            nav->system = nav->sel < m->nsys ? nav->sel : 0;
            dp_model_load_games(m, roms, nav->system);
            nav->level = 1;
            nav->sel = 0;
        } else if (scr == DP_SCR_SETTINGS) {
            if (nav->sel == 2 || nav->sel == 3 || nav->sel == 5)
                nav->settings_edit = nav->sel + 1;
            else if (nav->sel == 7)
                nav_shortcut(nav, 3);
            else if (nav->sel == 1) {
                nav_shortcut(nav, 5);
                m->input_test = 1;
                m->si.last_key[0] = '\0';
            } else if (nav->sel == 8 || nav->sel == 9)
                nav_shortcut(nav, 5);
            else if (nav->sel == 10)
                nav_shortcut(nav, 4);
            else if (nav->sel == 11)
                nav->sel = 2;
            else if (key != DP_KEY_X)
                nav_notice(nav, "Этот параметр только для чтения");
        } else if (scr == DP_SCR_MODULES && nav->sel < m->nmods) {
            nav->module_action = nav->sel + 1;
        } else if (scr == DP_SCR_GAMES && nav->sel < m->nroms &&
                   nav->system >= 0 && nav->system < m->nsys) {
            nav_launch(nav, m->systems[nav->system].id, m->rom_names[nav->sel], -1);
        } else if (scr == DP_SCR_CONTINUE) {
            if (m->ncont == 0 && key != DP_KEY_X) {
                nav_tab(nav, 1);
            } else if (nav->sel < m->ncont) {
                const struct dp_continue_item *it = &m->cont[nav->sel];
                if (it->sys_id[0] && it->rom[0])
                    nav_launch(nav, it->sys_id, it->rom, key == DP_KEY_X ? -1 : it->slot);
            }
        }
        break;
    case DP_KEY_B:
        if (nav->nback > 0) {
            nav->nback--;
            nav->tab = nav->back[nav->nback].tab;
            nav->sel = nav->back[nav->nback].sel;
        } else if (nav->level == 1) {
            nav->level = 0;
            nav->sel = nav->system;
        } else if (nav->tab != 0) {
            nav_tab(nav, 0);
        }
        break;
    default:
        break;
    }
    nav_clamp(nav, m);
    return 0;
}

static void nav_print(const struct dp_nav *nav)
{
    printf("screen=%s level=%d sel=%d system=%d\n", dp_screen_id((enum dp_screen)tab_screen(nav)),
           nav->level, nav->sel, nav->system);
}

static int write_ppm(const char *path, const struct dp_canvas *cv)
{
    FILE *f = fopen(path, "wb");
    if (!f)
        return -1;
    fprintf(f, "P6\n%d %d\n255\n", cv->w, cv->h);
    for (int i = 0; i < cv->w * cv->h; i++) {
        uint16_t p = cv->px[i];
        unsigned char rgb[3];
        rgb[0] = (unsigned char)(((p >> 11) & 0x1F) << 3);
        rgb[1] = (unsigned char)(((p >> 5) & 0x3F) << 2);
        rgb[2] = (unsigned char)((p & 0x1F) << 3);
        if (fwrite(rgb, 1, 3, f) != 3) {
            fclose(f);
            return -1;
        }
    }
    return fclose(f) == 0 ? 0 : -1;
}

static int open_display_at_start(struct dp_display *display, const char *path, int attempts)
{
    const struct timespec delay = { .tv_nsec = 100000000L };
    while (dp_display_open(display, path) != 0) {
        if (--attempts == 0)
            return -1;
        nanosleep(&delay, NULL);
    }
    return 0;
}

static int show_boot_splash(const char *out, const char *fb_path)
{
    struct dp_canvas canvas;
    if (dp_canvas_init(&canvas, DP_W, DP_H) != 0)
        return 1;
    dp_ui_boot_splash(&canvas);
    int rc = out && write_ppm(out, &canvas) != 0;
    if (!out || fb_path) {
        struct dp_display display;
        if (open_display_at_start(&display, fb_path, fb_path ? 1 : 9) != 0) {
            rc = 1;
        } else {
            if (dp_display_present(&display, &canvas) != 0)
                rc = 1;
            dp_display_close(&display);
        }
    }
    dp_canvas_free(&canvas);
    return rc;
}


/* ---- game launch: module hook + emulator command from emulators.toml ---- */

struct dp_launch_cfg {
    char cmd[512];
};

static int parse_emulators(const char *path, const char *system, struct dp_launch_cfg *cfg) {
    FILE *f = fopen(path, "r");
    char line[600];
    if (!f)
        return -1;
    while (fgets(line, sizeof(line), f)) {
        char *eq = strchr(line, '=');
        char *key = line;
        char *val;
        char *end;
        size_t klen;
        if (!eq)
            continue;
        *eq = '\0';
        val = eq + 1;
        while (*key == ' ' || *key == '\t')
            key++;
        klen = strlen(key);
        while (klen > 0 && (key[klen - 1] == ' ' || key[klen - 1] == '\t'))
            key[--klen] = '\0';
        while (*val == ' ' || *val == '\t')
            val++;
        end = val + strlen(val);
        while (end > val && (end[-1] == '\n' || end[-1] == '\r' || end[-1] == ' '))
            *--end = '\0';
        if (*val == '"')
            val++;
        if (end > val && end[-1] == '"')
            *--end = '\0';
        if (strcmp(key, system) == 0) {
            snprintf(cfg->cmd, sizeof(cfg->cmd), "%s", val);
            fclose(f);
            return 0;
        }
    }
    fclose(f);
    return 1;
}

static void replace_tag(const char *in, const char *tag, const char *value, char *out, size_t n) {
    const char *at = strstr(in, tag);
    size_t head;
    if (!at) {
        snprintf(out, n, "%s", in);
        return;
    }
    const char *tail = at + strlen(tag);
    if (at > in && (at[-1] == '\'' || at[-1] == '"') && *tail == at[-1]) {
        at--;
        tail++;
    }
    head = (size_t)(at - in);
    if (head >= n)
        head = n - 1;
    memcpy(out, in, head);
    out[head] = '\0';
    snprintf(out + head, n - head, "%s%s", value, tail);
}

static void expand_rom(const char *tmpl, int save_slot, char *out,
                       size_t n) {
    char slot[16];
    char step[1200];
    snprintf(slot, sizeof(slot), "%d", save_slot < 0 ? 0 : save_slot);
    replace_tag(tmpl, "%ROM%", "\"$1\"", step, sizeof(step));
    replace_tag(step, "%SLOT%", slot, out, n);
}

static int run_command(const char *cmd, const char *arg) {
    pid_t pid = fork();
    int status = 0;
    if (pid < 0)
        return -1;
    if (pid == 0) {
        execl("/bin/sh", "sh", "-c", cmd, "launcher", arg, (char *)NULL);
        _exit(127);
    }
    pid_t done;
    do {
        done = waitpid(pid, &status, 0);
    } while (done < 0 && errno == EINTR);
    if (done < 0)
        return -1;
    if (WIFEXITED(status))
        return WEXITSTATUS(status);
    return -1;
}

/* Keeps /data/continue.tsv honest after a game exits: the row for this ROM is
 * moved to the top with the slot we actually used, so "Продолжить" always
 * reflects the last session. Written atomically (tmp + fsync + rename). */
static void continue_update(const char *data_dir, const struct dp_model *m, const char *sys,
                            const char *rom, int slot)
{
    char path[1024];
    char tmp[1060];
    char lines[DP_MAX_CONTINUE][768];
    int nline = 0;

    if (strpbrk(rom, "\t\r\n") || strpbrk(sys, "\t\r\n"))
        return;
    snprintf(path, sizeof(path), "%s/continue.tsv", data_dir);
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);

    const char *title = rom;
    const char *system_name = sys;
    for (int i = 0; i < m->nsys; i++) {
        if (strcmp(m->systems[i].id, sys) == 0) {
            system_name = m->systems[i].name;
            break;
        }
    }

    FILE *f = fopen(path, "r");
    if (f) {
        char line[768];
        while (fgets(line, sizeof(line), f) && nline < DP_MAX_CONTINUE) {
            size_t len = strlen(line);
            while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
                line[--len] = '\0';
            if (!len || line[0] == '#')
                continue;
            /* drop the row we are about to rewrite */
            char copy[768];
            snprintf(copy, sizeof(copy), "%s", line);
            char *fields[7] = { 0 };
            int nf = 0;
            char *q = copy;
            fields[nf++] = q;
            for (; *q && nf < 7; q++) {
                if (*q == '\t') {
                    *q = '\0';
                    fields[nf++] = q + 1;
                }
            }
            if (nf >= 7 && strcmp(fields[5], sys) == 0 && strcmp(fields[6], rom) == 0)
                continue;
            snprintf(lines[nline], sizeof(lines[nline]), "%s", line);
            nline++;
        }
        fclose(f);
    }

    FILE *out = fopen(tmp, "w");
    if (!out) {
        fprintf(stderr, "launcher: cannot write %s\n", tmp);
        return;
    }
    fprintf(out, "%s\t%s\tнедавно\t%d\t%d\t%s\t%s\n", title, system_name, slot,
            slot >= 0 ? 1 : 0, sys, rom);
    int total = 1;
    for (int i = 0; i < nline && total < DP_MAX_CONTINUE; i++, total++)
        fprintf(out, "%s\n", lines[i]);
    fflush(out);
    fsync(fileno(out));
    fclose(out);

    if (rename(tmp, path) != 0) {
        fprintf(stderr, "launcher: cannot rename %s\n", tmp);
        return;
    }
    char dir[1024];
    snprintf(dir, sizeof(dir), "%s", data_dir);
    int dfd = open(dir, O_RDONLY);
    if (dfd >= 0) {
        fsync(dfd);
        close(dfd);
    }
}

static int launch_game(const struct dp_model *m, const char *roms, const char *mods_socket,
                       const char *emulators_path, const char *sys, const char *rom, int slot)
{
    struct dp_launch_cfg cfg;
    char rom_path[1024];
    char cmd[1200];
    int allow = 1;
    int child;

    dp_modc_launch(mods_socket, sys, rom, &allow);
    if (!allow) {
        printf("blocked\t%s\t%s\n", sys, rom);
        return 4;
    }
    if (parse_emulators(emulators_path, sys, &cfg) != 0 &&
        (strcmp(emulators_path, DEFAULT_EMULATORS) != 0 ||
         (parse_emulators(BUILTIN_EMULATORS, sys, &cfg) != 0 &&
          parse_emulators(IMPORTED_EMULATORS, sys, &cfg) != 0))) {
        fprintf(stderr, "launcher: no emulator for '%s' in %s\n", sys, emulators_path);
        return 5;
    }
    const char *folder = sys;
    for (int i = 0; i < m->nsys; i++) {
        if (strcmp(m->systems[i].id, sys) == 0) {
            folder = m->systems[i].folder;
            break;
        }
    }
    int len = snprintf(rom_path, sizeof(rom_path), "%s/%s/%s", roms, folder, rom);
    if (len < 0 || (size_t)len >= sizeof(rom_path))
        return 1;
    expand_rom(cfg.cmd, slot, cmd, sizeof(cmd));
    child = run_command(cmd, rom_path);
    printf("launch\t%s\t%s\tslot=%d\t%d\n", sys, rom, slot, child);
    if (child == 126 || child == 127)
        return 5;
    return child == 0 ? 0 : 1;
}

static int launch_selected(struct dp_nav *nav, struct dp_model *m, const char *roms,
                           const char *mods_socket, const char *emulators, const char *data)
{
    int rc = launch_game(m, roms, mods_socket, emulators, nav->lsys, nav->lrom, nav->lslot);
    if (rc == 0) {
        continue_update(data, m, nav->lsys, nav->lrom, nav->lslot);
        dp_model_load_continue(m, data);
        if (tab_screen(nav) == DP_SCR_CONTINUE)
            nav->sel = 0;
    }
    nav->launch = 0;
    return rc;
}

static int count_event_devices(void);
static void fill_sysinfo(struct dp_model *m, const char *fb_path, int details);

static void read_device_status(struct dp_model *m, const char *roms, const char *fb_path,
                               int details)
{
    time_t now = time(NULL);
    struct tm local;
    if (localtime_r(&now, &local))
        strftime(m->st.clock, sizeof(m->st.clock), "%H:%M", &local);

    struct statvfs fs;
    if (m->roms_ok && statvfs(roms, &fs) == 0) {
        m->rom_total_mb = (unsigned)((unsigned long long)fs.f_blocks * fs.f_frsize / 1048576);
        m->rom_used_mb = (unsigned)((unsigned long long)(fs.f_blocks - fs.f_bfree)
                                    * fs.f_frsize / 1048576);
    }

    m->st.battery = -1;
    m->st.charging = 0;
    DIR *supplies = opendir("/sys/class/power_supply");
    if (!supplies) {
        fill_sysinfo(m, fb_path, details);
        return;
    }
    struct dirent *entry;
    while ((entry = readdir(supplies)) != NULL) {
        if (entry->d_name[0] == '.')
            continue;
        char path[512];
        snprintf(path, sizeof(path), "/sys/class/power_supply/%s/capacity", entry->d_name);
        FILE *reading = fopen(path, "r");
        if (!reading)
            continue;
        int percent = -1;
        int have_capacity = fscanf(reading, "%d", &percent) == 1;
        fclose(reading);
        if (!have_capacity || percent < 0 || percent > 100)
            continue;
        m->st.battery = percent;
        snprintf(path, sizeof(path), "/sys/class/power_supply/%s/status", entry->d_name);
        reading = fopen(path, "r");
        if (reading) {
            char status[24];
            m->st.charging = fgets(status, sizeof(status), reading)
                && strcmp(status, "Charging\n") == 0;
            fclose(reading);
        }
        break;
    }
    closedir(supplies);
    fill_sysinfo(m, fb_path, details);
}

static int count_event_devices(void)
{
    DIR *d = opendir("/dev/input");
    int n = 0;
    struct dirent *e;
    if (!d)
        return 0;
    while ((e = readdir(d)) != NULL) {
        if (strncmp(e->d_name, "event", 5) == 0)
            n++;
    }
    closedir(d);
    return n;
}

static void read_first_line(const char *path, char *out, size_t n)
{
    out[0] = '\0';
    FILE *f = fopen(path, "r");
    if (!f)
        return;
    if (fgets(out, (int)n, f)) {
        char *nl = strchr(out, '\n');
        if (nl)
            *nl = '\0';
    }
    fclose(f);
}

static long read_number_file(const char *path)
{
    FILE *f = fopen(path, "r");
    long value = -1;
    if (!f)
        return -1;
    if (fscanf(f, "%ld", &value) != 1)
        value = -1;
    fclose(f);
    return value;
}

/* Real device facts for the INFO screen and the boot report; only meaningful
 * on the console, the host test passes explicit values instead. */
/* Bounded copy: keeps -Wformat-truncation= quiet and always terminates. */
static void copy_field(char *dst, size_t size, const char *src)
{
    size_t n = strlen(src);
    if (n >= size)
        n = size - 1;
    memcpy(dst, src, n);
    dst[n] = '\0';
}

static void fill_sysinfo(struct dp_model *m, const char *fb_path, int details)
{
    double uptime = 0.0;
    FILE *f = fopen("/proc/uptime", "r");
    if (f) {
        if (fscanf(f, "%lf", &uptime) != 1)
            uptime = 0.0;
        fclose(f);
    }
    unsigned long secs = (unsigned long)uptime;
    m->si.uptime_s = secs;

    unsigned long total_kb = 0, avail_kb = 0;
    f = fopen("/proc/meminfo", "r");
    if (f) {
        char line[128];
        while (fgets(line, sizeof(line), f)) {
            if (strncmp(line, "MemTotal:", 9) == 0)
                sscanf(line + 9, "%lu", &total_kb);
            else if (strncmp(line, "MemAvailable:", 13) == 0)
                sscanf(line + 13, "%lu", &avail_kb);
        }
        fclose(f);
    }
    m->si.mem_total_mb = (unsigned)(total_kb / 1024UL);
    m->si.mem_avail_mb = (unsigned)(avail_kb / 1024UL);

    int temp = -1;
    for (int zone = 0; zone < 8; zone++) {
        char path[96];
        snprintf(path, sizeof(path), "/sys/class/thermal/thermal_zone%d/temp", zone);
        long t = read_number_file(path);
        if (t > 0 && t < 1000)
            t *= 1000;
        if (t > 0 && t > temp)
            temp = (int)t;
    }
    m->si.temp_mc = temp;
    m->si.cpu_khz = read_number_file("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq");
    m->si.cpu_max_khz = read_number_file("/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq");
    m->si.gpu_hz = read_number_file("/sys/class/devfreq/ff400000.gpu/cur_freq");
    m->have_sysinfo = 1;
    if (!details)
        return;

    struct utsname u;
    if (uname(&u) == 0)
        copy_field(m->si.kernel, sizeof(m->si.kernel), u.release);

    char size[48];
    read_first_line("/sys/class/graphics/fb0/virtual_size", size, sizeof(size));
    long bpp = read_number_file("/sys/class/graphics/fb0/bits_per_pixel");
    if (size[0]) {
        for (char *p = size; *p; p++)
            if (*p == ',')
                *p = 'x';
        if (bpp > 0)
            snprintf(m->si.fb, sizeof(m->si.fb), "%s %ldbpp", size, bpp);
        else
            snprintf(m->si.fb, sizeof(m->si.fb), "%s", size);
    } else if (fb_path) {
        snprintf(m->si.fb, sizeof(m->si.fb), "%s", fb_path);
    }

    m->si.input_events = count_event_devices();
    struct dp_input in;
    if (dp_input_open(&in) == 0) {
        snprintf(m->si.input, sizeof(m->si.input), "%s", dp_input_name(&in));
        dp_input_close(&in);
    }
}

static void model_load_config(struct dp_model *m, const char *config_path)
{
    struct dp_config cfg;
    dp_config_init(&cfg);
    dp_config_load(&cfg, config_path);
    m->cfg_brightness = cfg.brightness;
    m->cfg_volume = cfg.volume;
    snprintf(m->cfg_profile, sizeof(m->cfg_profile), "%s", cfg.profile);
}

/* Prints the environment the launcher is about to work in; first thing to run
 * on a new device. */
static int selftest(const char *roms, const char *data, const char *emulators_path,
                    const char *mods_socket, const char *fb_path,
                    const char *config_path)
{
    struct dp_model *m = dp_model_new();
    if (!m)
        return 1;
    dp_model_scan(m, roms);
    dp_model_load_continue(m, data);
    dp_modc_status(mods_socket, m);
    model_load_config(m, config_path);
    fill_sysinfo(m, fb_path, 1);

    char temp[16] = "-";
    if (m->si.temp_mc >= 0)
        snprintf(temp, sizeof(temp), "%d.%d C",
                 m->si.temp_mc / 1000, (m->si.temp_mc % 1000) / 100);

    char uptime[24] = "-";
    if (m->si.uptime_s > 0) {
        unsigned long us = m->si.uptime_s;
        if (us < 60)
            snprintf(uptime, sizeof(uptime), "%lu s", us);
        else if (us < 3600)
            snprintf(uptime, sizeof(uptime), "%lu min", us / 60);
        else
            snprintf(uptime, sizeof(uptime), "%lu h %02lu", us / 3600, (us / 60) % 60);
    }

    printf("version=%s\n", DP_VERSION);
    printf("roms=%s systems=%d games=%u\n", roms, m->nsys, m->total_games);
    printf("data=%s continue=%d data_ok=%d\n", data, m->ncont, m->data_ok);
    printf("roms_ok=%d\n", m->roms_ok);
    printf("emulators=%s emulators_present=%d\n", emulators_path,
           access(emulators_path, R_OK) == 0 ? 1 : 0);
    printf("modd=%s modules=%d\n", mods_socket, m->nmods);
    printf("fb=%s fb_present=%d\n", fb_path, access(fb_path, F_OK) == 0 ? 1 : 0);
    printf("config=%s brightness=%d volume=%d profile=%s\n", config_path,
           m->cfg_brightness, m->cfg_volume,
           m->cfg_profile[0] ? m->cfg_profile : "balanced");
    printf("input_events=%d\n", m->si.input_events);
    printf("sysinfo kernel=%s uptime=%s mem=%u/%u MB temp=%s fb=%s input=%s\n",
           m->si.kernel[0] ? m->si.kernel : "-",
           uptime,
           m->si.mem_avail_mb, m->si.mem_total_mb, temp,
           m->si.fb[0] ? m->si.fb : "-",
           m->si.input[0] ? m->si.input : "-");
    printf("status=ok\n");
    dp_model_free(m);
    return 0;
}
static void boot_first_frame(void)
{
    static const char ticket[] = "/run/deepos-boot";
    puts("DEEPoS: launcher first frame");
    fflush(stdout);
    if (access("/run/deepos-boot-report", F_OK) == 0) {
        run_command("(/usr/local/bin/selfcheck.sh /flash/report/checks.txt --first-frame "
                    "&& rm -f /run/deepos-boot-report) </dev/null >/dev/null 2>&1 &", NULL);
    }
    if (access(ticket, R_OK) != 0)
        return;

    pid_t pid = fork();
    if (pid == 0) {
        execl("/usr/bin/updatr", "updatr", "--state", "/data", "good",
              "--boot-ticket", ticket, (char *)NULL);
        _exit(127);
    }
    int status;
    pid_t done = -1;
    if (pid > 0) {
        do {
            done = waitpid(pid, &status, 0);
        } while (done < 0 && errno == EINTR);
    }
    if (done < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        fprintf(stderr, "launcher: cannot confirm boot after first frame\n");
}

struct bench_stats {
    unsigned long long avg_us, p95_us, max_us;
};

static unsigned long long now_us(clockid_t clock_id)
{
    struct timespec ts;
    clock_gettime(clock_id, &ts);
    return (unsigned long long)ts.tv_sec * 1000000ull
           + (unsigned long long)ts.tv_nsec / 1000ull;
}

static int cmp_ull(const void *a, const void *b)
{
    const unsigned long long *x = a;
    const unsigned long long *y = b;
    return (*x < *y) ? -1 : (*x > *y);
}

static struct bench_stats bench_stats_of(unsigned long long *samples, int n)
{
    struct bench_stats st = { 0, 0, 0 };
    if (n <= 0)
        return st;
    unsigned long long sum = 0;
    for (int i = 0; i < n; i++)
        sum += samples[i];
    st.avg_us = sum / (unsigned long long)n;
    qsort(samples, (size_t)n, sizeof(samples[0]), cmp_ull);
    st.max_us = samples[n - 1];
    int idx = n * 95 / 100;
    if (idx >= n)
        idx = n - 1;
    st.p95_us = samples[idx];
    return st;
}

static void bench_write(const char *path, const char *bench_line, const char *device_line)
{
    FILE *f = fopen(path, "w");
    if (!f)
        return;
    fprintf(f, "%s\n%s\n", bench_line, device_line);
    fclose(f);
}

/* Repaint through the normal path so a pending notice is not swallowed. */
static void paint_nav(struct dp_canvas *cv, struct dp_model *m, struct dp_nav *nav)
{
    dp_ui_paint(cv, m, (enum dp_screen)tab_screen(nav), nav->system, nav->sel);
    if (nav->notice[0]) {
        dp_ui_toast(cv, nav->notice);
        nav->notice[0] = '\0';
    }
}

static void refresh_modules(struct dp_model *m, const char *socket)
{
    m->modules_online = dp_modc_status(socket, m) == 0;
}

static int apply_nav_actions(struct dp_nav *nav, struct dp_model *m, const char *config,
                             const char *sysfs, const char *data, const char *socket)
{
    if (!nav->module_action)
        return apply_selected_setting(nav, m, config, sysfs, data);

    const char *id = m->mods[nav->module_action - 1].id;
    nav->module_action = 0;
    if (strcmp(id, "thermal") == 0) {
        nav_shortcut(nav, 2);
        nav->sel = 5;
        return 1;
    }
    if (strcmp(id, "saves") != 0) {
        nav_notice(nav, "У модуля нет действий в меню");
        return 1;
    }
    if (nav->backup_pid > 0) {
        nav_notice(nav, "Копирование сейвов уже идёт");
        return 1;
    }
    if (dp_modc_action(socket, id, "backup") != 0) {
        nav_notice(nav, "Модуль не принял запрос");
        refresh_modules(m, socket);
        return 1;
    }

    const char *helper = "/usr/share/deepos/modules/saves/root/saves-backup.sh";
    char request_dir[512];
    snprintf(request_dir, sizeof(request_dir), "%s/module-data/saves", data);
    if (access(helper, R_OK) != 0) {
        nav_notice(nav, "Запрос передан модулю");
        return 1;
    }
    nav->backup_pid = fork();
    if (nav->backup_pid == 0) {
        execl("/bin/sh", "sh", helper, request_dir, (char *)NULL);
        _exit(127);
    }
    nav_notice(nav, nav->backup_pid > 0 ? "Копирование сейвов…" : "Копирование не запустилось");
    return 1;
}

/* Numbers the user will later take from the console: full repaint cost, the
 * fb present cost, and the latency between the kernel event timestamp and the
 * frame that shows it. */
static int bench_run(struct dp_canvas *cv, struct dp_model *m, struct dp_nav *nav,
                     struct dp_display *disp, const char *out_path, int frames)
{
    enum { MAX_FRAMES = 256, MAX_PRESSES = 20 };
    unsigned long long paint[MAX_FRAMES], present[MAX_FRAMES], latency[MAX_PRESSES];
    int npaint = 0, npresent = 0, npresses = 0;
    if (frames < 1)
        frames = 60;
    if (frames > MAX_FRAMES)
        frames = MAX_FRAMES;

    for (int i = 0; i < frames; i++) {
        unsigned long long t0 = now_us(CLOCK_MONOTONIC);
        paint_nav(cv, m, nav);
        paint[npaint++] = now_us(CLOCK_MONOTONIC) - t0;
        if (disp) {
            t0 = now_us(CLOCK_MONOTONIC);
            dp_display_present(disp, cv);
            present[npresent++] = now_us(CLOCK_MONOTONIC) - t0;
        }
    }

    struct dp_input in;
    int have_in = dp_input_open(&in) == 0 && in.ready;
    if (have_in) {
        unsigned long long started = now_us(CLOCK_MONOTONIC);
        while (npresses < MAX_PRESSES
               && now_us(CLOCK_MONOTONIC) - started < 30000000ull) {
            if (disp) {
                paint_nav(cv, m, nav);
                dp_ui_overlay(cv, "Замер задержки", "Нажмите любую кнопку",
                              "Собирается до 20 нажатий", npresses, MAX_PRESSES);
                dp_display_present(disp, cv);
            }
            enum dp_key k = dp_input_poll(&in, 500);
            if (!in.ready)
                break;
            if (k == DP_KEY_NONE)
                continue;
            if (in.last_us == 0)
                continue;
            unsigned long long t = now_us(CLOCK_REALTIME) - in.last_us;
            if (t < 1000000ull)
                latency[npresses++] = t;
        }
        dp_input_close(&in);
    }

    struct bench_stats ps = bench_stats_of(paint, npaint);
    struct bench_stats ds = bench_stats_of(present, npresent);
    struct bench_stats ls = bench_stats_of(latency, npresses);

    char bench_line[512];
    snprintf(bench_line, sizeof(bench_line),
             "bench version=%s frames=%d paint_avg_us=%llu paint_p95_us=%llu "
             "paint_max_us=%llu present_avg_us=%llu present_p95_us=%llu "
             "present_max_us=%llu presses=%d latency_avg_us=%llu latency_p95_us=%llu "
             "latency_max_us=%llu",
             DP_VERSION, npaint, ps.avg_us, ps.p95_us, ps.max_us,
             ds.avg_us, ds.p95_us, ds.max_us, npresses,
             ls.avg_us, ls.p95_us, ls.max_us);

    char device_line[256];
    snprintf(device_line, sizeof(device_line), "device kernel=%s fb=%s input=%s",
             m->si.kernel[0] ? m->si.kernel : "-",
             m->si.fb[0] ? m->si.fb : (disp ? "fb" : "-"),
             m->si.input[0] ? m->si.input : (have_in ? "unknown" : "-"));

    puts(bench_line);
    puts(device_line);
    fflush(stdout);

    if (out_path) {
        bench_write(out_path, bench_line, device_line);
    } else {
        mkdir("/flash/report", 0755);
        FILE *probe = fopen("/flash/report/bench.txt", "a");
        if (probe) {
            fclose(probe);
            bench_write("/flash/report/bench.txt", bench_line, device_line);
        } else {
            mkdir("/data/report", 0755);
            bench_write("/data/report/bench.txt", bench_line, device_line);
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *roms = "/storage";
    const char *data = "/data";
    const char *screen = "continue";
    const char *out = NULL;
    int system_index = 0;
    int battery = -1;
    int charging = 0;
    const char *clock = "";
    unsigned rom_used = 0, rom_total = 0;
    const char *keys = NULL;
    int print_state = 0;
    const char *mods_socket = "/run/modd.sock";
    int print_modules = 0;
    const char *fb_path = NULL;
    const char *module_action = NULL;
    const char *run_game = NULL;
    const char *emulators_path = DEFAULT_EMULATORS;
    int save_slot = -1;
    char config_buf[512];
    const char *config_path = NULL;
    snprintf(config_buf, sizeof(config_buf), "/data/config/settings.toml");
    const char *sysfs_prefix = NULL;
    const char *set_kv = NULL;
    int print_config = 0;
    int do_apply = 0;
    int bench_frames = 0;
    int boot_splash = 0;
    const char *bench_out = NULL;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        #define NEED_ARG() (i + 1 < argc ? argv[++i] : (usage(), exit(2), ""))
        if (strcmp(a, "--roms") == 0) roms = NEED_ARG();
        else if (strcmp(a, "--data") == 0) data = NEED_ARG();
        else if (strcmp(a, "--screen") == 0) screen = NEED_ARG();
        else if (strcmp(a, "--out") == 0) out = NEED_ARG();
        else if (strcmp(a, "--boot-splash") == 0) boot_splash = 1;
        else if (strcmp(a, "--system") == 0) system_index = atoi(NEED_ARG());
        else if (strcmp(a, "--battery") == 0) battery = atoi(NEED_ARG());
        else if (strcmp(a, "--charging") == 0) charging = 1;
        else if (strcmp(a, "--clock") == 0) clock = NEED_ARG();
        else if (strcmp(a, "--rom-used") == 0) rom_used = (unsigned)atoi(NEED_ARG());
        else if (strcmp(a, "--rom-total") == 0) rom_total = (unsigned)atoi(NEED_ARG());
        else if (strcmp(a, "--keys") == 0) keys = NEED_ARG();
        else if (strcmp(a, "--print-state") == 0) print_state = 1;
        else if (strcmp(a, "--modules-socket") == 0) mods_socket = NEED_ARG();
        else if (strcmp(a, "--print-modules") == 0) print_modules = 1;
        else if (strcmp(a, "--fb") == 0) fb_path = NEED_ARG();
        else if (strcmp(a, "--module-action") == 0) module_action = NEED_ARG();
        else if (strcmp(a, "--run-game") == 0) run_game = NEED_ARG();
        else if (strcmp(a, "--emulators") == 0) emulators_path = NEED_ARG();
        else if (strcmp(a, "--save-slot") == 0) save_slot = atoi(NEED_ARG());
        else if (strcmp(a, "--config") == 0) config_path = NEED_ARG();
        else if (strcmp(a, "--sysfs") == 0) sysfs_prefix = NEED_ARG();
        else if (strcmp(a, "--set") == 0) set_kv = NEED_ARG();
        else if (strcmp(a, "--print-config") == 0) print_config = 1;
        else if (strcmp(a, "--apply") == 0) do_apply = 1;
        else if (strcmp(a, "--bench") == 0) bench_frames = atoi(NEED_ARG());
        else if (strcmp(a, "--bench-out") == 0) bench_out = NEED_ARG();
        else if (strcmp(a, "--list") == 0) {
            for (int s = 0; s < DP_SCR_COUNT; s++)
                printf("%s\n", dp_screen_id((enum dp_screen)s));
            return 0;
        } else if (strcmp(a, "--selftest") == 0) {
            return selftest(roms, data, emulators_path, mods_socket,
                            fb_path ? fb_path : "/dev/fb0", config_path);
        } else if (strcmp(a, "--list-roms") == 0) {
            struct dp_model *lm = dp_model_new();
            if (!lm)
                return 1;
            dp_model_scan(lm, roms);
            for (int s = 0; s < lm->nsys; s++)
                printf("%s\t%u\t%s\n", lm->systems[s].id, lm->systems[s].games,
                       lm->systems[s].name);
            printf("TOTAL\t%u\t%d\n", lm->total_games, lm->nsys);
            dp_model_free(lm);
            return 0;
        } else if (strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0) {
            usage();
            return 0;
        } else {
            fprintf(stderr, "launcher: unknown option %s\n", a);
            usage();
            return 2;
        }
        #undef NEED_ARG
    }

    if (boot_splash)
        return show_boot_splash(out, fb_path);

    if (!config_path) {
        snprintf(config_buf, sizeof(config_buf), "%s/config/settings.toml", data);
        config_path = config_buf;
    }

    if (set_kv || print_config || do_apply) {
        struct dp_config cfg;
        char line[128];
        dp_config_init(&cfg);
        dp_config_load(&cfg, config_path);
        if (set_kv) {
            int rc = dp_config_set(&cfg, set_kv);
            if (rc < 0) {
                fprintf(stderr, "launcher: bad value in '%s'\n", set_kv);
                return 2;
            }
            if (rc == 0) {
                fprintf(stderr, "launcher: unknown setting in '%s'\n", set_kv);
                return 2;
            }
            if (dp_config_save(&cfg, config_path) != 0) {
                fprintf(stderr, "launcher: cannot save %s\n", config_path);
                return 1;
            }
        }
        if (do_apply) {
            char profile_path[512];
            int n;
            snprintf(profile_path, sizeof(profile_path), "%s/cpu-profile", data);
            n = dp_config_apply(&cfg, sysfs_prefix, profile_path);
            printf("applied=%d\n", n);
        }
        dp_config_format(&cfg, line, (int)sizeof(line));
        printf("config %s\n", line);
        return 0;
    }

    int scr = dp_screen_from_id(screen);
    if (scr < 0) {
        fprintf(stderr, "launcher: unknown screen '%s'\n", screen);
        return 2;
    }

    struct dp_model *m = dp_model_new();
    if (!m) {
        fputs("launcher: out of memory\n", stderr);
        return 1;
    }
    if (dp_model_scan(m, roms) < 0)
        fprintf(stderr, "launcher: cannot read ROMs at %s (empty library)\n", roms);
    dp_model_load_continue(m, data);
    refresh_modules(m, mods_socket);
    model_load_config(m, config_path);

    /* Input diagnostics, in a child so the UI never waits: the report lists
     * every /dev/input node with its capabilities and then every raw event for
     * the first 40 s of this boot. The user only has to press the buttons. */
    if (argc == 1 && access("/flash/INPUT.PROBE", F_OK) == 0) {
        mkdir("/flash/report", 0755);
        pid_t logger = fork();
        if (logger == 0) {
            struct dp_input probe;
            if (dp_input_open(&probe) == 0) {
                dp_input_scan("/flash/report/input.txt");
                dp_input_probe(&probe, 40, "/flash/report/input.txt");
                dp_input_close(&probe);
            } else {
                dp_input_scan("/flash/report/input.txt");
            }
            _exit(0);
        }
    }

    if (run_game) {
        char spec[512];
        char sys[32];
        char rom[DP_ROM_NAME];
        int rc_game;
        snprintf(spec, sizeof(spec), "%s", run_game);
        char *colon = strchr(spec, ':');
        if (!colon) {
            fprintf(stderr, "launcher: --run-game needs SYSTEM:ROM\n");
            dp_model_free(m);
            return 2;
        }
        *colon = '\0';
        copy_field(sys, sizeof(sys), spec);
        copy_field(rom, sizeof(rom), colon + 1);
        rc_game = launch_game(m, roms, mods_socket, emulators_path, sys, rom, save_slot);
        if (rc_game == 0)
            continue_update(data, m, sys, rom, save_slot);
        dp_model_free(m);
        return rc_game;
    }

    if (module_action) {
        char spec[128];
        snprintf(spec, sizeof(spec), "%s", module_action);
        char *colon = strchr(spec, ':');
        if (!colon) {
            fprintf(stderr, "launcher: --module-action needs ID:ACTION\n");
            dp_model_free(m);
            return 2;
        }
        *colon = '\0';
        int ok = dp_modc_action(mods_socket, spec, colon + 1) == 0;
        printf("%s\t%s\t%s\n", spec, colon + 1, ok ? "ok" : "failed");
        dp_model_free(m);
        return ok ? 0 : 1;
    }

    if (print_modules) {
        for (int i = 0; i < m->nmods; i++)
            printf("%s\t%s\n", m->mods[i].id, m->mods[i].state);
        dp_model_free(m);
        return 0;
    }

    m->st.battery = battery;
    m->st.charging = charging;
    snprintf(m->st.clock, sizeof(m->st.clock), "%s", clock);
    m->rom_used_mb = rom_used;
    m->rom_total_mb = rom_total;
    if (argc == 1)
        read_device_status(m, roms, "/dev/fb0", 1);

    struct dp_canvas cv;
    if (dp_canvas_init(&cv, DP_W, DP_H) != 0) {
        dp_model_free(m);
        fputs("launcher: canvas init failed\n", stderr);
        return 1;
    }

    struct dp_nav nav = { 0 };
    nav.tab = tab_from_screen(scr);
    if (scr == DP_SCR_GAMES) {
        nav.level = 1;
        nav.system = system_index >= 0 && system_index < m->nsys ? system_index : 0;
        dp_model_load_games(m, roms, nav.system);
    }

    int quit = 0;
    if (keys) {
        char buf[512];
        snprintf(buf, sizeof(buf), "%s", keys);
        for (char *tok = strtok(buf, ", ;"); tok && !quit && !nav.launch;
             tok = strtok(NULL, ", ;")) {
            enum dp_key k = dp_key_from_name(tok);
            if (k == DP_KEY_NONE) {
                fprintf(stderr, "launcher: unknown key '%s'\n", tok);
                dp_canvas_free(&cv);
                dp_model_free(m);
                return 2;
            }
            quit = nav_key(&nav, m, roms, k);
            if (!quit)
                apply_nav_actions(&nav, m, config_path, sysfs_prefix, data, mods_socket);
        }
    }

    if (nav.launch) {
        int rc_game = launch_selected(&nav, m, roms, mods_socket, emulators_path, data);
        dp_canvas_free(&cv);
        dp_model_free(m);
        return rc_game;
    }

    if (print_state || (keys && !out && !fb_path)) {
        nav_print(&nav);
        dp_canvas_free(&cv);
        dp_model_free(m);
        return quit ? 0 : 0;
    }

    if (bench_frames > 0) {
        struct dp_display bdisp;
        int have_bdisp = fb_path && dp_display_open(&bdisp, fb_path) == 0;
        int brc = bench_run(&cv, m, &nav, have_bdisp ? &bdisp : NULL, bench_out, bench_frames);
        if (have_bdisp)
            dp_display_close(&bdisp);
        dp_canvas_free(&cv);
        dp_model_free(m);
        return brc;
    }

    paint_nav(&cv, m, &nav);

    int rc = 0;
    if (out && write_ppm(out, &cv) != 0) {
        fprintf(stderr, "launcher: cannot write %s\n", out);
        rc = 1;
    }

    struct dp_display disp;
    int have_disp = open_display_at_start(&disp, fb_path, argc == 1 ? 9 : 1) == 0;
    if ((fb_path || !out) && !have_disp) {
        fprintf(stderr, "launcher: no display (%s)\n", fb_path ? fb_path : "/dev/fb0");
        if (fb_path)
            rc = 1;
    }
    if (have_disp) {
        if (dp_display_present(&disp, &cv) != 0) {
            fprintf(stderr, "launcher: cannot present the frame\n");
            rc = 1;
        } else if (argc == 1 && !disp.fake) {
            if (access("/flash/BENCH.ON", F_OK) == 0) {
                bench_run(&cv, m, &nav, &disp, NULL, 60);
                if (rename("/flash/BENCH.ON", "/flash/BENCH.DONE") != 0)
                    fprintf(stderr, "launcher: cannot rename BENCH.ON\n");
            }
            boot_first_frame();
        }
    }

    if (!out && !fb_path) {
        struct dp_input in;
        pid_t sound = 0;
        if (dp_input_open(&in) == 0) {
            unsigned long long sample_at = 0;
            while (!quit && in.ready) {
                enum dp_key k = dp_input_poll(&in, 250);
                if (sound > 0 && waitpid(sound, NULL, WNOHANG) == sound)
                    sound = 0;
                int old_tab = nav.tab, old_level = nav.level, old_sel = nav.sel;
                int changed = 0;
                if (k != DP_KEY_NONE) {
                    quit = nav_key(&nav, m, roms, k);
                    if (quit)
                        break;
                    changed = apply_nav_actions(&nav, m, config_path, sysfs_prefix, data, mods_socket);
                    if (tab_screen(&nav) == DP_SCR_INFO) {
                        if (!m->input_test)
                            snprintf(m->si.last_key, sizeof(m->si.last_key), "%s", dp_key_name(k));
                        changed = 1;
                    }
                }
                if (nav.backup_pid > 0) {
                    int status = 0;
                    if (waitpid(nav.backup_pid, &status, WNOHANG) == nav.backup_pid) {
                        nav.backup_pid = 0;
                        nav_notice(&nav, WIFEXITED(status) && WEXITSTATUS(status) == 0 ?
                                   "Копия сейвов создана" : "Ошибка копирования сейвов");
                    }
                }
                unsigned long long now = now_us(CLOCK_MONOTONIC);
                if (tab_screen(&nav) == DP_SCR_INFO && (nav.tab != old_tab || now >= sample_at)) {
                    read_device_status(m, roms, "/dev/fb0", 0);
                    sample_at = now + 1000000;
                    changed = 1;
                }
                if (tab_screen(&nav) == DP_SCR_MODULES && nav.tab != old_tab) {
                    refresh_modules(m, mods_socket);
                    nav_clamp(&nav, m);
                }
                int game_status = -1;
                if (nav.launch) {
                    dp_sound_stop(sound);
                    sound = 0;
                    /* Drop queued gameplay and quit-combo events before returning to the menu. */
                    dp_input_close(&in);
                    if (have_disp) {
                        dp_display_close(&disp);
                        have_disp = 0;
                    }
                    game_status = launch_selected(&nav, m, roms, mods_socket, emulators_path, data);
                    have_disp = dp_display_open(&disp, NULL) == 0;
                    dp_input_open(&in);
                    changed = 1;
                }
                if (!changed && !nav.notice[0]
                    && nav.tab == old_tab && nav.level == old_level && nav.sel == old_sel)
                    continue;
                int have_notice = nav.notice[0] != '\0';
                paint_nav(&cv, m, &nav);
                if (game_status > 0) {
                    const char *message = game_status == 5 ? "Нет эмулятора для этой системы" :
                                          game_status == 4 ? "Запуск отклонён модулем" :
                                          "Не удалось запустить игру";
                    dp_ui_toast(&cv, message);
                }
                if (have_disp)
                    dp_display_present(&disp, &cv);
                if (have_disp && !disp.fake && argc == 1 && game_status < 0 && !m->input_test) {
                    if ((k == DP_KEY_L1 || k == DP_KEY_L2 || k == DP_KEY_R1 || k == DP_KEY_R2) &&
                        nav.tab != old_tab)
                        sound = dp_sound_play(sound, DP_TONE_TAB);
                    else if (k == DP_KEY_B && (nav.tab != old_tab || nav.level != old_level))
                        sound = dp_sound_play(sound, DP_TONE_BACK);
                    else if ((k == DP_KEY_A || k == DP_KEY_START) && !have_notice)
                        sound = dp_sound_play(sound, DP_TONE_CONFIRM);
                }
            }
            if (in.lost)
                fprintf(stderr, "launcher: input device lost\n");
            dp_input_close(&in);
        } else if (!have_disp) {
            printf("screen=%s systems=%d games=%u continue=%d\n",
                   dp_screen_id((enum dp_screen)scr), m->nsys, m->total_games, m->ncont);
        }
        dp_sound_stop(sound);
    }
    if (have_disp)
        dp_display_close(&disp);

    dp_canvas_free(&cv);
    dp_model_free(m);
    return rc;
}
