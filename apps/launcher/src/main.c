/* DEEPoS launcher - prototype entry point (renders one screen to a PPM file). */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
#include "dp_display.h"
#include "dp_input.h"
#include "dp_config.h"
#include "dp_modc.h"
#include "dp_model.h"
#include "dp_theme.h"
#include "dp_ui.h"

static void usage(void)
{
    puts("usage: launcher [options]\n"
         "  --roms DIR        ROM library root (default /storage/roms)\n"
         "  --data DIR        DEEPoS data dir (default /data)\n"
         "  --screen NAME     continue|systems|games|settings|modules|files|info\n"
         "  --out FILE.ppm    write the rendered frame (P6)\n"
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

struct dp_nav {
    int tab;        /* 0 continue, 1 games, 2 settings, 3 modules, 4 files, 5 info */
    int level;      /* games tab: 0 = system list, 1 = game list */
    int sel;
    int system;
    int launch;     /* set when the user asked to start a game */
    char lsys[32];
    char lrom[64];
    int lslot;
    int settings_edit; /* card index + 1, applied after the key */
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
    if (scr == DP_SCR_GAMES && nav->system < m->nsys)
        return (int)m->systems[nav->system].games;
    if (scr == DP_SCR_SETTINGS)
        return 12;
    if (scr == DP_SCR_MODULES)
        return 5;
    if (scr == DP_SCR_FILES)
        return 6;
    return 0;
}

/* Settings cards that own a value: brightness, volume and the cpu profile.
 * A press cycles the value, writes settings.toml and applies it right away. */
static int settings_edit_card(struct dp_model *m, int card, const char *config_path,
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
    dp_config_save(&cfg, config_path);
    dp_config_apply(&cfg, sysfs_prefix, profile_path);
    m->cfg_brightness = cfg.brightness;
    m->cfg_volume = cfg.volume;
    snprintf(m->cfg_profile, sizeof(m->cfg_profile), "%s", cfg.profile);
    return 1;
}

/* Returns 1 when the launcher should quit. */
static int nav_key(struct dp_nav *nav, const struct dp_model *m, enum dp_key key)
{
    int rows = row_count(m, nav);
    int scr = tab_screen(nav);
    switch (key) {
    case DP_KEY_QUIT:
        return 1;
    case DP_KEY_LEFT:
        if (!(scr == DP_SCR_GAMES))
            nav->tab = (nav->tab + TABS_COUNT - 1) % TABS_COUNT;
        break;
    case DP_KEY_RIGHT:
        if (!(scr == DP_SCR_GAMES))
            nav->tab = (nav->tab + 1) % TABS_COUNT;
        break;
    case DP_KEY_UP:
        nav->sel = nav->sel > 0 ? nav->sel - 1 : 0;
        break;
    case DP_KEY_DOWN:
        if (rows > 0 && nav->sel + 1 < rows)
            nav->sel++;
        break;
    case DP_KEY_A:
        if (scr == DP_SCR_SYSTEMS && m->nsys > 0) {
            nav->system = nav->sel < m->nsys ? nav->sel : 0;
            nav->level = 1;
            nav->sel = 0;
        } else if (scr == DP_SCR_SETTINGS && nav->sel < 12) {
            nav->settings_edit = nav->sel + 1;
        } else if (scr == DP_SCR_CONTINUE && nav->sel < m->ncont) {
            const struct dp_continue_item *it = &m->cont[nav->sel];
            if (it->rom[0]) {
                snprintf(nav->lsys, sizeof(nav->lsys), "%s", it->sys_id);
                snprintf(nav->lrom, sizeof(nav->lrom), "%s", it->rom);
                nav->lslot = it->slot;
                nav->launch = 1;
            }
        }
        break;
    case DP_KEY_B:
        if (nav->level == 1) {
            nav->level = 0;
            nav->sel = nav->system;
        }
        break;
    default:
        break;
    }
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
    head = (size_t)(at - in);
    if (head >= n)
        head = n - 1;
    memcpy(out, in, head);
    out[head] = '\0';
    snprintf(out + head, n - head, "%s%s", value, at + strlen(tag));
}

static void expand_rom(const char *tmpl, const char *rom_path, int save_slot, char *out,
                       size_t n) {
    char slot[16];
    char step[1200];
    snprintf(slot, sizeof(slot), "%d", save_slot < 0 ? 0 : save_slot);
    replace_tag(tmpl, "%ROM%", rom_path, step, sizeof(step));
    replace_tag(step, "%SLOT%", slot, out, n);
}

static int run_command(const char *cmd) {
    pid_t pid = fork();
    int status = 0;
    if (pid < 0)
        return -1;
    if (pid == 0) {
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        _exit(127);
    }
    if (waitpid(pid, &status, 0) < 0)
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
    char lines[DP_MAX_CONTINUE][512];
    int nline = 0;

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
        char line[512];
        while (fgets(line, sizeof(line), f) && nline < DP_MAX_CONTINUE) {
            size_t len = strlen(line);
            while (len && (line[len - 1] == '\n' || line[len - 1] == '\r'))
                line[--len] = '\0';
            if (!len || line[0] == '#')
                continue;
            /* drop the row we are about to rewrite */
            char copy[512];
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

static int launch_game(const char *roms, const char *mods_socket, const char *emulators_path,
                       const char *sys, const char *rom, int slot)
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
    if (parse_emulators(emulators_path, sys, &cfg) != 0) {
        fprintf(stderr, "launcher: no emulator for '%s' in %s\n", sys, emulators_path);
        return 5;
    }
    snprintf(rom_path, sizeof(rom_path), "%s/%s/%s", roms, sys, rom);
    expand_rom(cfg.cmd, rom_path, slot, cmd, sizeof(cmd));
    child = run_command(cmd);
    printf("launch\t%s\t%s\tslot=%d\t%d\n", sys, rom, slot, child);
    return child == 0 ? 0 : 1;
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

/* Prints the environment the launcher is about to work in; first thing to run
 * on a new device. */
static void model_load_config(struct dp_model *m, const char *config_path)
{
    struct dp_config cfg;
    dp_config_init(&cfg);
    dp_config_load(&cfg, config_path);
    m->cfg_brightness = cfg.brightness;
    m->cfg_volume = cfg.volume;
    snprintf(m->cfg_profile, sizeof(m->cfg_profile), "%s", cfg.profile);
}

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

    printf("version=0.4\n");
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
    printf("input_events=%d\n", count_event_devices());
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
                    "&& rm -f /run/deepos-boot-report) </dev/null >/dev/null 2>&1 &");
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

int main(int argc, char **argv)
{
    const char *roms = "/storage";
    const char *data = "/data";
    const char *screen = "continue";
    const char *out = NULL;
    int system_index = 0;
    int battery = 78;
    int charging = 0;
    const char *clock = "14:32";
    unsigned rom_used = 12, rom_total = 36;
    const char *keys = NULL;
    int print_state = 0;
    const char *mods_socket = "/run/modd.sock";
    int print_modules = 0;
    const char *fb_path = NULL;
    const char *module_action = NULL;
    const char *run_game = NULL;
    const char *emulators_path = "/data/emulators.toml";
    int save_slot = -1;
    char config_buf[512];
    const char *config_path = NULL;
    snprintf(config_buf, sizeof(config_buf), "/data/config/settings.toml");
    const char *sysfs_prefix = "";
    const char *set_kv = NULL;
    int print_config = 0;
    int do_apply = 0;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        #define NEED_ARG() (i + 1 < argc ? argv[++i] : (usage(), exit(2), ""))
        if (strcmp(a, "--roms") == 0) roms = NEED_ARG();
        else if (strcmp(a, "--data") == 0) data = NEED_ARG();
        else if (strcmp(a, "--screen") == 0) screen = NEED_ARG();
        else if (strcmp(a, "--out") == 0) out = NEED_ARG();
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
    dp_modc_status(mods_socket, m);
    model_load_config(m, config_path);

    if (run_game) {
        char spec[512];
        char sys[32];
        char rom[128];
        int rc_game;
        snprintf(spec, sizeof(spec), "%s", run_game);
        char *colon = strchr(spec, ':');
        if (!colon) {
            fprintf(stderr, "launcher: --run-game needs SYSTEM:ROM\n");
            dp_model_free(m);
            return 2;
        }
        *colon = '\0';
        snprintf(sys, sizeof(sys), "%s", spec);
        snprintf(rom, sizeof(rom), "%s", colon + 1);
        rc_game = launch_game(roms, mods_socket, emulators_path, sys, rom, save_slot);
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

    struct dp_canvas cv;
    if (dp_canvas_init(&cv, DP_W, DP_H) != 0) {
        dp_model_free(m);
        fputs("launcher: canvas init failed\n", stderr);
        return 1;
    }

    struct dp_nav nav = { 0 };
    nav.tab = tab_from_screen(scr);
    nav.level = 0;
    nav.sel = system_index;
    nav.system = system_index;

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
            quit = nav_key(&nav, m, k);
            if (!quit && nav.settings_edit) {
                settings_edit_card(m, nav.settings_edit - 1, config_path,
                                   sysfs_prefix, data);
                nav.settings_edit = 0;
            }
        }
    }

    if (nav.launch) {
        int rc_game = launch_game(roms, mods_socket, emulators_path, nav.lsys, nav.lrom,
                                  nav.lslot);
        if (rc_game == 0)
            continue_update(data, m, nav.lsys, nav.lrom, nav.lslot);
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

    dp_ui_paint(&cv, m, (enum dp_screen)tab_screen(&nav), nav.system, nav.sel);

    int rc = 0;
    if (out && write_ppm(out, &cv) != 0) {
        fprintf(stderr, "launcher: cannot write %s\n", out);
        rc = 1;
    }

    struct dp_display disp;
    int have_disp = dp_display_open(&disp, fb_path) == 0;
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
            boot_first_frame();
        }
    }

    if (!out && !fb_path) {
        struct dp_input in;
        if (dp_input_open(&in) == 0) {
            while (!quit && !nav.launch) {
                enum dp_key k = dp_input_poll(&in, 250);
                if (k == DP_KEY_NONE)
                    continue;
                quit = nav_key(&nav, m, k);
                dp_ui_paint(&cv, m, (enum dp_screen)tab_screen(&nav), nav.system, nav.sel);
                if (have_disp)
                    dp_display_present(&disp, &cv);
            }
            dp_input_close(&in);
        } else if (!have_disp) {
            printf("screen=%s systems=%d games=%u continue=%d\n",
                   dp_screen_id((enum dp_screen)scr), m->nsys, m->total_games, m->ncont);
        }
    }
    if (have_disp)
        dp_display_close(&disp);

    dp_canvas_free(&cv);
    dp_model_free(m);
    return rc;
}
