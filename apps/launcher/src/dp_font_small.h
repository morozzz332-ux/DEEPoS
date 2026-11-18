/* DEEPoS launcher - 11 px small bitmap font table (generated tables + API). */
#ifndef DP_FONT_SMALL_H
#define DP_FONT_SMALL_H

#include <stdint.h>

#define DP_SMALL_ADV 7
#define DP_SMALL_ROWS 14

struct dp_glyph_small {
    uint32_t codepoint;
    uint16_t rows[DP_SMALL_ROWS];
};

const struct dp_glyph_small *dp_font_small_lookup(unsigned int codepoint);
int dp_font_small_cell(void);

#endif /* DP_FONT_SMALL_H */
