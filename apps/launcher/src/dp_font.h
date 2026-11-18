/* DEEPoS launcher - 13 px body bitmap font table (generated tables + API). */
#ifndef DP_FONT_H
#define DP_FONT_H

#include <stdint.h>

#define DP_GLYPH_ADV 8
#define DP_GLYPH_ROWS 17

struct dp_glyph {
    uint32_t codepoint;
    uint16_t rows[DP_GLYPH_ROWS];
};

const struct dp_glyph *dp_font_lookup(unsigned int codepoint);
int dp_font_cell(void);

#endif /* DP_FONT_H */
