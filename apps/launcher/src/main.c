/* DEEPoS launcher - prototype entry point (renders one screen to a PPM file). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
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
         "  --list            list available screens\n"
         "  --list-roms       list detected ROM systems with game counts\n");
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

    dp_ui_paint(&cv, m, (enum dp_screen)scr, system_index, 0);

    int rc = 0;
    if (out && write_ppm(out, &cv) != 0) {
        fprintf(stderr, "launcher: cannot write %s\n", out);
        rc = 1;
    } else if (!out) {
        printf("screen=%s systems=%d games=%u continue=%d\n", dp_screen_id((enum dp_screen)scr),
               m->nsys, m->total_games, m->ncont);
    }

    dp_canvas_free(&cv);
    dp_model_free(m);
    return rc;
}
