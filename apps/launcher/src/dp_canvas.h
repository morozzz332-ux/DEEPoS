/* DEEPoS launcher - RGB565 software canvas. */
#ifndef DP_CANVAS_H
#define DP_CANVAS_H

#include <stdint.h>

struct dp_canvas {
    int w;
    int h;
    uint16_t *px;
};

uint16_t dp565(int r, int g, int b);

int dp_canvas_init(struct dp_canvas *cv, int w, int h);
void dp_canvas_free(struct dp_canvas *cv);

void dp_fill(struct dp_canvas *cv, uint16_t color);
void dp_rect(struct dp_canvas *cv, int x, int y, int w, int h, uint16_t color);
void dp_frame(struct dp_canvas *cv, int x, int y, int w, int h, uint16_t color);
void dp_hline(struct dp_canvas *cv, int x, int y, int w, uint16_t color);
void dp_vline(struct dp_canvas *cv, int x, int y, int h, uint16_t color);

/* Draws UTF-8 text; scale 1 = 12x12 cell. Returns the advance width in pixels. */
int dp_text(struct dp_canvas *cv, int x, int y, const char *utf8, uint16_t color, int scale);
int dp_text_w(const char *utf8, int scale);

/* Same as above with the 8x8 font (tabs, hints, secondary labels). */
int dp_text_small(struct dp_canvas *cv, int x, int y, const char *utf8, uint16_t color, int scale);
int dp_text_small_w(const char *utf8, int scale);

#endif /* DP_CANVAS_H */
