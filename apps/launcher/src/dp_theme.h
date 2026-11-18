/* DEEPoS launcher - palette and layout tokens (see SPEC §6). */
#ifndef DP_THEME_H
#define DP_THEME_H

#include "dp_canvas.h"

#define DP_W 640
#define DP_H 480

/* rows: status bar, section header, hint bar */
#define DP_STATUS_H 30
#define DP_HEADER_H 26
#define DP_HINT_H 26
#define DP_BODY_Y (DP_STATUS_H)
#define DP_BODY_H (DP_H - DP_STATUS_H - DP_HINT_H)

#define DP_COL_BG       dp565(0x0C, 0x10, 0x0E)
#define DP_COL_PANEL    dp565(0x13, 0x1A, 0x16)
#define DP_COL_PANEL2   dp565(0x18, 0x22, 0x1C)
#define DP_COL_LINE     dp565(0x20, 0x2A, 0x24)
#define DP_COL_FG       dp565(0xE9, 0xED, 0xE7)
#define DP_COL_FG2      dp565(0x98, 0xA6, 0x9D)
#define DP_COL_FG3      dp565(0x5F, 0x6D, 0x65)
#define DP_COL_ACC      dp565(0x79, 0xD8, 0x9A)
#define DP_COL_SEL      dp565(0x18, 0x24, 0x1D)
#define DP_COL_WARN     dp565(0xE6, 0xB2, 0x5C)
#define DP_COL_BAD      dp565(0xE0, 0x70, 0x6A)

#endif /* DP_THEME_H */
