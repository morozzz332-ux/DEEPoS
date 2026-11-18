#include "dp_canvas.h"
#include "dp_font.h"
#include "dp_font_small.h"

#include <stdlib.h>
#include <string.h>

uint16_t dp565(int r, int g, int b)
{
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3));
}

int dp_canvas_init(struct dp_canvas *cv, int w, int h)
{
    if (!cv || w <= 0 || h <= 0)
        return -1;
    cv->px = calloc((size_t)w * (size_t)h, sizeof(uint16_t));
    if (!cv->px)
        return -1;
    cv->w = w;
    cv->h = h;
    return 0;
}

void dp_canvas_free(struct dp_canvas *cv)
{
    if (!cv)
        return;
    free(cv->px);
    cv->px = NULL;
    cv->w = cv->h = 0;
}

void dp_fill(struct dp_canvas *cv, uint16_t color)
{
    size_t n = (size_t)cv->w * (size_t)cv->h;
    for (size_t i = 0; i < n; i++)
        cv->px[i] = color;
}

void dp_rect(struct dp_canvas *cv, int x, int y, int w, int h, uint16_t color)
{
    if (w <= 0 || h <= 0)
        return;
    int x0 = x < 0 ? 0 : x;
    int y0 = y < 0 ? 0 : y;
    int x1 = x + w > cv->w ? cv->w : x + w;
    int y1 = y + h > cv->h ? cv->h : y + h;
    for (int yy = y0; yy < y1; yy++) {
        uint16_t *row = cv->px + (size_t)yy * (size_t)cv->w;
        for (int xx = x0; xx < x1; xx++)
            row[xx] = color;
    }
}

void dp_frame(struct dp_canvas *cv, int x, int y, int w, int h, uint16_t color)
{
    dp_rect(cv, x, y, w, 1, color);
    dp_rect(cv, x, y + h - 1, w, 1, color);
    dp_rect(cv, x, y, 1, h, color);
    dp_rect(cv, x + w - 1, y, 1, h, color);
}

void dp_hline(struct dp_canvas *cv, int x, int y, int w, uint16_t color)
{
    dp_rect(cv, x, y, w, 1, color);
}

void dp_vline(struct dp_canvas *cv, int x, int y, int h, uint16_t color)
{
    dp_rect(cv, x, y, 1, h, color);
}

/* Decodes one UTF-8 codepoint; *len receives the number of consumed bytes. */
static unsigned int dp_utf8_next(const char *s, int *len)
{
    const unsigned char *p = (const unsigned char *)s;
    if (p[0] < 0x80) {
        *len = 1;
        return p[0];
    }
    if ((p[0] & 0xE0) == 0xC0) {
        *len = 2;
        return ((unsigned)p[0] & 0x1F) << 6 | (p[1] & 0x3F);
    }
    if ((p[0] & 0xF0) == 0xE0) {
        *len = 3;
        return ((unsigned)p[0] & 0x0F) << 12 | ((unsigned)p[1] & 0x3F) << 6 | (p[2] & 0x3F);
    }
    if ((p[0] & 0xF8) == 0xF0) {
        *len = 4;
        return ((unsigned)p[0] & 0x07) << 18 | ((unsigned)p[1] & 0x3F) << 12 |
               ((unsigned)p[2] & 0x3F) << 6 | (p[3] & 0x3F);
    }
    *len = 1;
    return '?';
}

int dp_text_w(const char *utf8, int scale)
{
    int n = 0;
    for (const char *p = utf8; *p;) {
        int len = 0;
        dp_utf8_next(p, &len);
        p += len;
        n++;
    }
    return n * DP_GLYPH_ADV * scale;
}

int dp_text(struct dp_canvas *cv, int x, int y, const char *utf8, uint16_t color, int scale)
{
    if (!utf8 || scale <= 0)
        return 0;
    int pen = x;
    for (const char *p = utf8; *p;) {
        int len = 0;
        unsigned int cp = dp_utf8_next(p, &len);
        p += len;
        const struct dp_glyph *g = dp_font_lookup(cp);
        if (g) {
            for (int gy = 0; gy < DP_GLYPH_ROWS; gy++) {
                uint16_t bits = g->rows[gy];
                if (!bits)
                    continue;
                for (int gx = 0; gx < DP_GLYPH_ADV; gx++) {
                    if (!(bits & (1u << (DP_GLYPH_ADV - 1 - gx))))
                        continue;
                    dp_rect(cv, pen + gx * scale, y + gy * scale, scale, scale, color);
                }
            }
        }
        pen += DP_GLYPH_ADV * scale;
    }
    return pen - x;
}

int dp_text_small_w(const char *utf8, int scale)
{
    int n = 0;
    for (const char *p = utf8; *p;) {
        int len = 0;
        dp_utf8_next(p, &len);
        p += len;
        n++;
    }
    return n * DP_SMALL_ADV * scale;
}

int dp_text_small(struct dp_canvas *cv, int x, int y, const char *utf8, uint16_t color, int scale)
{
    if (!utf8 || scale <= 0)
        return 0;
    int pen = x;
    for (const char *p = utf8; *p;) {
        int len = 0;
        unsigned int cp = dp_utf8_next(p, &len);
        p += len;
        const struct dp_glyph_small *g = dp_font_small_lookup(cp);
        if (g) {
            for (int gy = 0; gy < DP_SMALL_ROWS; gy++) {
                uint16_t bits = g->rows[gy];
                if (!bits)
                    continue;
                for (int gx = 0; gx < DP_SMALL_ADV; gx++) {
                    if (!(bits & (1u << (DP_SMALL_ADV - 1 - gx))))
                        continue;
                    dp_rect(cv, pen + gx * scale, y + gy * scale, scale, scale, color);
                }
            }
        }
        pen += DP_SMALL_ADV * scale;
    }
    return pen - x;
}