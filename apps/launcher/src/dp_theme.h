/* DEEPoS launcher - palette and layout tokens (see SPEC §6). */
#ifndef DP_THEME_H
#define DP_THEME_H

#include "dp_canvas.h"

#define DP_VERSION "0.38-v20"

#define DP_W 640
#define DP_H 480

/* rows: status bar, section header, hint bar */
#define DP_STATUS_H 32
#define DP_HEADER_H 34
#define DP_HINT_H 28
#define DP_PAD 12

#define DP_COL_BG       dp565(0x0C, 0x10, 0x0E)
#define DP_COL_PANEL    dp565(0x13, 0x1A, 0x16)
#define DP_COL_PANEL2   dp565(0x1C, 0x27, 0x21)
#define DP_COL_LINE     dp565(0x2A, 0x38, 0x30)
#define DP_COL_FG       dp565(0xEE, 0xF2, 0xEC)
#define DP_COL_FG2      dp565(0xB7, 0xC4, 0xBA)
#define DP_COL_FG3      dp565(0x8B, 0x9B, 0x90)
#define DP_COL_ACC      dp565(0x79, 0xD8, 0x9A)
#define DP_COL_SEL      dp565(0x1F, 0x32, 0x27)
#define DP_COL_WARN     dp565(0xE6, 0xB2, 0x5C)
#define DP_COL_BAD      dp565(0xE0, 0x70, 0x6A)

#endif /* DP_THEME_H */
