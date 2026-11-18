/* DEEPoS launcher - prototype entry point (renders one screen to a PPM file). */
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
#include "dp_display.h"
#include "dp_input.h"
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
         "  --list-roms       list detected ROM systems with game counts\n");
}

#define TABS_COUNT 6

struct dp_nav {
    int tab;        /* 0 continue, 1 games, 2 settings, 3 modules, 4 files, 5 info */
    int level;      /* games tab: 0 = system list, 1 = game list */
    int sel;
    int system;
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
    return 0;
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

int main(int argc, char **argv)
{
    const char *roms = "/storage/roms";
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
        else if (strcmp(a, "--list") == 0) {
            for (int s = 0; s < DP_SCR_COUNT; s++)
                printf("%s\n", dp_screen_id((enum dp_screen)s));
            return 0;
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

    if (run_game) {
        char spec[512];
        char sys[32];
        char rom[128];
        char rom_path[1024];
        char cmd[1200];
        struct dp_launch_cfg cfg;
        int allow = 1;
        int child;
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

        dp_modc_launch(mods_socket, sys, rom, &allow);
        if (!allow) {
            printf("blocked\t%s\t%s\n", sys, rom);
            dp_model_free(m);
            return 4;
        }
        if (parse_emulators(emulators_path, sys, &cfg) != 0) {
            fprintf(stderr, "launcher: no emulator for '%s' in %s\n", sys, emulators_path);
            dp_model_free(m);
            return 5;
        }
        snprintf(rom_path, sizeof(rom_path), "%s/%s/%s", roms, sys, rom);
        expand_rom(cfg.cmd, rom_path, save_slot, cmd, sizeof(cmd));
        child = run_command(cmd);
        printf("launch\t%s\t%s\tslot=%d\t%d\n", sys, rom, save_slot, child);
        dp_model_free(m);
        return child == 0 ? 0 : 1;
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

    struct dp_nav nav;
    nav.tab = tab_from_screen(scr);
    nav.level = 0;
    nav.sel = system_index;
    nav.system = system_index;

    int quit = 0;
    if (keys) {
        char buf[512];
        snprintf(buf, sizeof(buf), "%s", keys);
        for (char *tok = strtok(buf, ", ;"); tok && !quit; tok = strtok(NULL, ", ;")) {
            enum dp_key k = dp_key_from_name(tok);
            if (k == DP_KEY_NONE) {
                fprintf(stderr, "launcher: unknown key '%s'\n", tok);
                dp_canvas_free(&cv);
                dp_model_free(m);
                return 2;
            }
            quit = nav_key(&nav, m, k);
        }
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
        }
    }

    if (!out && !fb_path) {
        struct dp_input in;
        if (dp_input_open(&in) == 0) {
            while (!quit) {
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
