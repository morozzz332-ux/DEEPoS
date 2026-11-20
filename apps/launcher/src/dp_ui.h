/* DEEPoS launcher - screen painters. */
#ifndef DP_UI_H
#define DP_UI_H

#include "dp_canvas.h"
#include "dp_clock.h"
#include "dp_cores.h"
#include "dp_model.h"

enum dp_screen {
    DP_SCR_CONTINUE = 0,
    DP_SCR_SYSTEMS,
    DP_SCR_GAMES,
    DP_SCR_SETTINGS,
    DP_SCR_MODULES,
    DP_SCR_FILES,
    DP_SCR_INFO,
    DP_SCR_COUNT
};

const char *dp_screen_id(enum dp_screen s);
int dp_screen_from_id(const char *id);

/* Paints one screen into an already allocated 640x480 canvas. */
void dp_ui_paint(struct dp_canvas *cv, const struct dp_model *m, enum dp_screen scr,
                 int system_index, int selected);

/* Draws the branded frame before the device starts the interactive launcher. */
void dp_ui_boot_splash(struct dp_canvas *cv);

/* Transient message above the hint bar (failed launch, read-only card, ...). */
void dp_ui_toast(struct dp_canvas *cv, const char *message);
void dp_ui_module_details(struct dp_canvas *cv, const struct dp_module_info *module,
                          const char *message);
void dp_ui_clock(struct dp_canvas *cv, int region, int selected, const struct tm *draft);
void dp_ui_cores(struct dp_canvas *cv, const char *system, const struct dp_cores *list, int selected);

/* Centred panel for the guided hardware measurement (BENCH.ON on BOOT). */
void dp_ui_overlay(struct dp_canvas *cv, const char *title, const char *line1,
                   const char *line2, int done, int total);

#endif /* DP_UI_H */
