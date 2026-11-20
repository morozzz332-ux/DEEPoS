/* DEEPoS launcher - palette and layout tokens (see SPEC §6). */
#ifndef DP_THEME_H
#define DP_THEME_H

#include "dp_canvas.h"

#define DP_VERSION "0.41-v20-test"

#define DP_W 640
#define DP_H 480

/* rows: status bar, section header, hint bar */
#define DP_STATUS_H 32
#define DP_HEADER_H 34
#define DP_HINT_H 28
#define DP_PAD 12
/* The LCD sits under a plastic bezel: keep a few pixels of air at the top
 * and bottom so tabs and the hint bar are not covered by it. */
#define DP_SAFE_TOP 8
#define DP_SAFE_BOTTOM 12
#define DP_BODY_Y0 (DP_SAFE_TOP + DP_STATUS_H + DP_HEADER_H)
#define DP_BODY_Y1 (DP_H - DP_SAFE_BOTTOM - DP_HINT_H)

#define DP_COL_BG       dp565(0x08, 0x14, 0x0A)
#define DP_COL_PANEL    dp565(0x10, 0x21, 0x10)
#define DP_COL_PANEL2   dp565(0x1A, 0x30, 0x18)
#define DP_COL_LINE     dp565(0x38, 0x58, 0x2D)
#define DP_COL_FG       dp565(0xD0, 0xF8, 0xA8)
#define DP_COL_FG2      dp565(0xA3, 0xDA, 0x7D)
#define DP_COL_FG3      dp565(0x82, 0xB3, 0x68)
#define DP_COL_ACC      dp565(0xB8, 0xF4, 0x72)
#define DP_COL_SEL      dp565(0x28, 0x43, 0x1E)
#define DP_COL_WARN     dp565(0xE6, 0xB2, 0x5C)
#define DP_COL_BAD      dp565(0xE0, 0x70, 0x6A)

#endif /* DP_THEME_H */
