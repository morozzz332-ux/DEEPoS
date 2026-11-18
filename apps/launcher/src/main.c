/* DEEPoS launcher - prototype entry point (renders one screen to a PPM file). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
#include "dp_input.h"
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

    if (print_state || (keys && !out)) {
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
    } else if (!out) {
        struct dp_input in;
        if (dp_input_open(&in) == 0) {
            while (!quit) {
                enum dp_key k = dp_input_poll(&in, 250);
                if (k == DP_KEY_NONE)
                    continue;
                quit = nav_key(&nav, m, k);
                dp_ui_paint(&cv, m, (enum dp_screen)tab_screen(&nav), nav.system, nav.sel);
            }
            dp_input_close(&in);
        } else {
            printf("screen=%s systems=%d games=%u continue=%d\n",
                   dp_screen_id((enum dp_screen)scr), m->nsys, m->total_games, m->ncont);
        }
    }

    dp_canvas_free(&cv);
    dp_model_free(m);
    return rc;
}
