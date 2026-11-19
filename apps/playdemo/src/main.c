/* DEEPoS demo - the smallest possible "game" that proves the whole chain.
 *
 * It is launched by the launcher through emulators.toml exactly like a real
 * emulator, draws into /dev/fb0 through the same dp_canvas/dp_display code and
 * reads the same evdev keys. If this program runs on the console after a game
 * press, then the library, the emulator table, exec, fbdev and input all work.
 *
 * Host usage (tests, no device):
 *   playdemo --fb frame.bin --keys "DOWN,A,DOWN,B" --exit-after 4
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dp_canvas.h"
#include "dp_display.h"
#include "dp_input.h"
#include "dp_theme.h"

static void paint(struct dp_canvas *cv, int level, int presses, const char *rom)
{
    dp_fill(cv, DP_COL_BG);
    dp_rect(cv, 0, 0, cv->w, DP_STATUS_H, DP_COL_PANEL);
    dp_text_small(cv, 12, 9, "DEEPoS demo", DP_COL_FG, 1);
    dp_text_small(cv, cv->w - 12 - dp_text_small_w("B - выход", 1), 9, "B - выход",
                  DP_COL_FG2, 1);

    dp_text(cv, 24, 60, "Экран и кнопки работают", DP_COL_FG, 1);
    dp_text_small(cv, 24, 84, rom && rom[0] ? rom : "(без файла)", DP_COL_FG3, 1);

    /* Bar graph: every UP/DOWN press changes the level. */
    for (int i = 0; i < 10; i++) {
        int x = 24 + i * 58;
        int h = 40 + i * (level + 1) * 3;
        if (h > 260)
            h = 260;
        dp_rect(cv, x, 400 - h, 46, h, i <= level ? DP_COL_ACC : DP_COL_PANEL2);
    }

    char buf[64];
    snprintf(buf, sizeof(buf), "нажатий: %d", presses);
    dp_text_small(cv, 24, 418, buf, DP_COL_FG2, 1);
    dp_text_small(cv, 24, 440, "B - выход, START+SELECT - тоже", DP_COL_FG3, 1);
}

int main(int argc, char **argv)
{
    const char *fb_path = NULL;
    const char *keys = NULL;
    const char *rom = "";
    int exit_after = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fb") == 0 && i + 1 < argc)
            fb_path = argv[++i];
        else if (strcmp(argv[i], "--keys") == 0 && i + 1 < argc)
            keys = argv[++i];
        else if (strcmp(argv[i], "--exit-after") == 0 && i + 1 < argc)
            exit_after = atoi(argv[++i]);
        else if (argv[i][0] != '-')
            rom = argv[i];
    }

    struct dp_canvas cv;
    if (dp_canvas_init(&cv, DP_W, DP_H) != 0) {
        fputs("playdemo: canvas init failed\n", stderr);
        return 1;
    }

    struct dp_display disp;
    if (dp_display_open(&disp, fb_path) != 0) {
        fprintf(stderr, "playdemo: no display (%s)\n", fb_path ? fb_path : "/dev/fb0");
        dp_canvas_free(&cv);
        return 1;
    }

    int level = 3;
    int presses = 0;
    int done = 0;

    if (keys && keys[0]) {
        char buf[512];
        snprintf(buf, sizeof(buf), "%s", keys);
        char *save = NULL;
        for (char *tok = strtok_r(buf, ", ;", &save); tok; tok = strtok_r(NULL, ", ;", &save)) {
            enum dp_key k = dp_key_from_name(tok);
            if (k == DP_KEY_UP && level < 9)
                level++;
            else if (k == DP_KEY_DOWN && level > 0)
                level--;
            else if (k == DP_KEY_B || k == DP_KEY_QUIT)
                done = 1;
            presses++;
            if (exit_after && presses >= exit_after)
                break;
        }
    } else {
        struct dp_input in;
        if (dp_input_open(&in) == 0) {
            while (!done && in.ready) {
                enum dp_key k = dp_input_poll(&in, 250);
                if (k == DP_KEY_UP && level < 9)
                    level++;
                else if (k == DP_KEY_DOWN && level > 0)
                    level--;
                else if (k == DP_KEY_B || k == DP_KEY_QUIT)
                    done = 1;
                else
                    continue;
                presses++;
                paint(&cv, level, presses, rom);
                dp_display_present(&disp, &cv);
            }
            dp_input_close(&in);
        } else {
            /* No keypad (host without evdev): leave after one drawn frame. */
            done = 1;
        }
    }

    paint(&cv, level, presses, rom);
    dp_display_present(&disp, &cv);
    dp_display_close(&disp);
    dp_canvas_free(&cv);
    printf("playdemo: rom=%s presses=%d level=%d done=%d\n",
           rom[0] ? rom : "-", presses, level, done);
    return 0;
}
