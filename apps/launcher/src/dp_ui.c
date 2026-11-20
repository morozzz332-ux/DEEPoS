#include "dp_ui.h"

#include <stdio.h>
#include <string.h>

#include "dp_font.h"
#include "dp_font_small.h"
#include "dp_theme.h"

#define DP_TABS 6

static const char *const dp_tabs[DP_TABS] = {
    "Продолжить", "Игры", "Настройки", "Модули", "Файлы", "Сведения",
};

/* Screens "systems" and "games" share the same tab. */
static int dp_tab_index(enum dp_screen scr)
{
    switch (scr) {
    case DP_SCR_CONTINUE: return 0;
    case DP_SCR_SYSTEMS:
    case DP_SCR_GAMES: return 1;
    case DP_SCR_SETTINGS: return 2;
    case DP_SCR_MODULES: return 3;
    case DP_SCR_FILES: return 4;
    case DP_SCR_INFO: return 5;
    default: return 0;
    }
}

const char *dp_screen_id(enum dp_screen s)
{
    switch (s) {
    case DP_SCR_CONTINUE: return "continue";
    case DP_SCR_SYSTEMS: return "systems";
    case DP_SCR_GAMES: return "games";
    case DP_SCR_SETTINGS: return "settings";
    case DP_SCR_MODULES: return "modules";
    case DP_SCR_FILES: return "files";
    case DP_SCR_INFO: return "info";
    default: return "?";
    }
}

int dp_screen_from_id(const char *id)
{
    for (int i = 0; i < DP_SCR_COUNT; i++) {
        if (strcmp(id, dp_screen_id((enum dp_screen)i)) == 0)
            return i;
    }
    return -1;
}

/* ---------------------------------------------------------------- widgets */

static size_t dp_utf8_size(const char *s)
{
    unsigned char lead = (unsigned char)*s;
    if (lead < 0x80)
        return 1;
    size_t n = lead < 0xC2 ? 0 : lead < 0xE0 ? 2 : lead < 0xF0 ? 3 : lead <= 0xF4 ? 4 : 0;
    for (size_t i = 1; i < n; i++) {
        if (((unsigned char)s[i] & 0xC0) != 0x80)
            return 0;
    }
    return n;
}

static void dp_text_fit(struct dp_canvas *cv, int x, int y, int width,
                        const char *s, uint16_t color, int small)
{
    const int cells = (width > DP_W ? DP_W : width) / (small ? DP_SMALL_ADV : DP_GLYPH_ADV);
    char text[4 * (DP_W / DP_SMALL_ADV) + 1];
    size_t used = 0, last = 0;
    if (cells <= 0)
        return;
    for (int i = 0; i < cells && *s; i++) {
        last = used;
        size_t n = dp_utf8_size(s);
        if (n) {
            memcpy(text + used, s, n);
            used += n;
            s += n;
        } else {
            text[used++] = '?';
            s++;
        }
    }
    if (*s)
        memcpy(text + last, "…", sizeof("…"));
    else
        text[used] = '\0';
    if (small)
        dp_text_small(cv, x, y, text, color, 1);
    else
        dp_text(cv, x, y, text, color, 1);
}

struct dp_hint {
    const char *key;
    const char *label;
};

static int dp_keycap(struct dp_canvas *cv, int x, int y, const char *label)
{
    int w = dp_text_small_w(label, 1) + 12;
    dp_rect(cv, x, y, w, 18, DP_COL_PANEL2);
    dp_frame(cv, x, y, w, 18, DP_COL_LINE);
    dp_text_small(cv, x + 6, y + 2, label, DP_COL_FG, 1);
    return w;
}

static void dp_hints(struct dp_canvas *cv, const struct dp_hint *items, int n,
                     const char *back_label)
{
    int y = DP_H - DP_SAFE_BOTTOM - DP_HINT_H + 5;
    dp_rect(cv, 0, DP_BODY_Y1, DP_W, DP_HINT_H, DP_COL_PANEL);
    dp_hline(cv, 0, DP_BODY_Y1, DP_W, DP_COL_LINE);
    int limit = DP_W - 12;
    if (back_label)
        limit -= dp_text_small_w(back_label, 1) + 40;
    int x = DP_PAD;
    for (int i = 0; i < n; i++) {
        int kw = dp_text_small_w(items[i].key, 1) + 12;
        int lw = dp_text_small_w(items[i].label, 1);
        if (x + kw + 6 + lw > limit)
            break;
        dp_keycap(cv, x, y, items[i].key);
        dp_text_small(cv, x + kw + 6, y + 2, items[i].label, DP_COL_FG2, 1);
        x += kw + 6 + lw + 16;
    }
    if (back_label) {
        int kw = dp_text_small_w("B", 1) + 12;
        int lw = dp_text_small_w(back_label, 1);
        int bx = DP_W - DP_PAD - kw - 6 - lw;
        dp_keycap(cv, bx, y, "B");
        dp_text_small(cv, bx + kw + 6, y + 2, back_label, DP_COL_FG2, 1);
    }
}

static void dp_statusbar(struct dp_canvas *cv, const struct dp_model *m, enum dp_screen active)
{
    dp_rect(cv, 0, DP_SAFE_TOP, DP_W, DP_STATUS_H, DP_COL_PANEL);
    dp_hline(cv, 0, DP_SAFE_TOP + DP_STATUS_H - 1, DP_W, DP_COL_LINE);

    int cur = dp_tab_index(active);
    int x = DP_PAD;
    for (int i = 0; i < DP_TABS; i++) {
        int tw = dp_text_w(dp_tabs[i], 1);
        uint16_t col = DP_COL_FG2;
        if (i == cur) {
            dp_rect(cv, x - 4, DP_SAFE_TOP + 4, tw + 8, 24, DP_COL_ACC);
            col = DP_COL_BG;
        }
        dp_text(cv, x, DP_SAFE_TOP + 7, dp_tabs[i], col, 1);
        x += tw + 14;
    }

    const char *clock = m->st.clock;
    if (clock[0]) {
        int cw = dp_text_small_w(clock, 1);
        dp_text_small(cv, DP_W - DP_PAD - cw, DP_SAFE_TOP + 9, clock, DP_COL_FG2, 1);
    }
    if (m->st.battery < 0)
        return;

    char buf[16];
    snprintf(buf, sizeof(buf), "%d%%", m->st.battery);
    int pw = dp_text_small_w(buf, 1);
    int cw = clock[0] ? dp_text_small_w(clock, 1) + 10 : 0;
    int bx = DP_W - DP_PAD - cw - pw - 8 - 26;
    dp_frame(cv, bx, DP_SAFE_TOP + 10, 24, 12, DP_COL_FG3);
    dp_rect(cv, bx + 1, DP_SAFE_TOP + 11, 22, 10, DP_COL_BG);
    int pct = m->st.battery > 100 ? 100 : m->st.battery;
    dp_rect(cv, bx + 1, DP_SAFE_TOP + 11, 22 * pct / 100, 10,
            pct <= 20 ? DP_COL_BAD : DP_COL_ACC);
    if (m->st.charging) {
        dp_rect(cv, bx + 9, DP_SAFE_TOP + 13, 2, 6, DP_COL_WARN);
        dp_rect(cv, bx + 12, DP_SAFE_TOP + 13, 2, 4, DP_COL_WARN);
    }
    dp_text_small(cv, bx - 8 - pw, DP_SAFE_TOP + 9, buf, DP_COL_FG2, 1);
}

static void dp_section(struct dp_canvas *cv, const char *title, const char *meta)
{
    int y = DP_SAFE_TOP + DP_STATUS_H;
    int right = DP_W - DP_PAD;
    if (meta) {
        int mw = dp_text_small_w(meta, 1);
        dp_text_small(cv, right - mw, y + 11, meta, DP_COL_FG2, 1);
        right -= mw + 14;
    }
    dp_text_fit(cv, DP_PAD, y + 7, right - DP_PAD, title, DP_COL_FG, 0);
    dp_hline(cv, 0, y + DP_HEADER_H - 1, DP_W, DP_COL_LINE);
}

static void dp_row_frame(struct dp_canvas *cv, int x, int y, int w, int h, int selected)
{
    if (!selected)
        return;
    dp_rect(cv, x, y, w, h, DP_COL_SEL);
    dp_rect(cv, x, y, 3, h, DP_COL_ACC);
}

static int dp_first_visible(int selected, int rows)
{
    return selected < rows ? 0 : selected - rows + 1;
}

static void dp_scrollbar(struct dp_canvas *cv, int x, int y, int h, int total,
                         int visible, int first)
{
    if (total <= visible || h <= 0)
        return;
    int thumb = h * visible / total;
    if (thumb < 14)
        thumb = 14;
    int span = h - thumb;
    int pos = span * first / (total - visible);
    dp_rect(cv, x, y, 2, h, DP_COL_LINE);
    dp_rect(cv, x, y + pos, 2, thumb, DP_COL_FG3);
}

static void dp_empty(struct dp_canvas *cv, const char *title, const char *message)
{
    const int y = (DP_BODY_Y0 + DP_BODY_Y1) / 2 - 26;
    dp_text(cv, (DP_W - dp_text_w(title, 1)) / 2, y, title, DP_COL_FG, 1);
    if (message)
        dp_text(cv, (DP_W - dp_text_w(message, 1)) / 2, y + 26, message, DP_COL_FG2, 1);
}

static void dp_initials(const char *title, char out[9])
{
    size_t used = 0;
    int words = 0, start = 1;
    for (const char *p = title; *p && words < 2;) {
        size_t n = dp_utf8_size(p);
        if (strchr(" :-", *p)) {
            start = 1;
        } else if (start) {
            if (n > 1) {
                memcpy(out + used, p, n);
                used += n;
            } else {
                out[used++] = *p >= 'a' && *p <= 'z' ? (char)(*p - 'a' + 'A') : (n ? *p : '?');
            }
            start = 0;
            words++;
        }
        p += n ? n : 1;
    }
    if (!used)
        out[used++] = '-';
    out[used] = '\0';
}

/* ---------------------------------------------------------------- screens */

static const char *dp_count_word(unsigned n, const char *one, const char *few, const char *many)
{
    unsigned m100 = n % 100, m10 = n % 10;
    if (m100 >= 11 && m100 <= 14)
        return many;
    if (m10 == 1)
        return one;
    if (m10 >= 2 && m10 <= 4)
        return few;
    return many;
}

static const char *dp_games_word(unsigned n)
{
    return dp_count_word(n, "игра", "игры", "игр");
}

static void dp_library_summary(char *out, size_t size, const struct dp_model *m)
{
    snprintf(out, size, "%d %s · %u %s", m->nsys,
             dp_count_word((unsigned)m->nsys, "система", "системы", "систем"),
             m->total_games, dp_games_word(m->total_games));
}

static void dp_screen_continue(struct dp_canvas *cv, const struct dp_model *m, int selected)
{
    char meta[48];
    snprintf(meta, sizeof(meta), "%d %s", m->ncont, dp_games_word((unsigned)m->ncont));
    dp_section(cv, "ПРОДОЛЖИТЬ", meta);

    if (m->ncont == 0) {
        dp_empty(cv, "Нет недавних игр", "Запущенные игры появятся здесь");
        const struct dp_hint items[] = { { "A", "Открыть игры" } };
        dp_hints(cv, items, 1, NULL);
        return;
    }

    const int y0 = DP_BODY_Y0 + 2;
    const int rh = 40;
    const int rows = (DP_BODY_Y1 - 6 - y0) / rh;
    const int first = dp_first_visible(selected, rows);
    int y = y0;
    for (int i = first; i < m->ncont && i < first + rows; i++) {
        const struct dp_continue_item *it = &m->cont[i];
        dp_row_frame(cv, 8, y, DP_W - 16, rh - 2, i == selected);

        char ini[9];
        dp_initials(it->title, ini);
        dp_rect(cv, 20, y + 5, 36, 28, DP_COL_PANEL2);
        int iw = dp_text_w(ini, 1);
        dp_text(cv, 20 + (36 - iw) / 2, y + 11, ini, DP_COL_ACC, 1);
        dp_text_fit(cv, 66, y + 3, 400, it->title, DP_COL_FG, 0);
        dp_text_fit(cv, 66, y + 22, 400, it->system, DP_COL_FG2, 1);

        int mx = DP_W - 20 - dp_text_small_w(it->meta, 1);
        dp_text_small(cv, mx, y + 5, it->meta, DP_COL_FG3, 1);

        if (it->has_save) {
            char badge[20];
            if (it->slot >= 0)
                snprintf(badge, sizeof(badge), "СЛОТ %d", it->slot);
            else
                snprintf(badge, sizeof(badge), "АВТОСЕЙВ");
            int bw = dp_text_small_w(badge, 1) + 10;
            int bx = DP_W - 20 - bw;
            dp_frame(cv, bx, y + 20, bw, 17, DP_COL_LINE);
            dp_text_small(cv, bx + 5, y + 22, badge, DP_COL_FG2, 1);
        }
        y += rh;
    }
    dp_scrollbar(cv, DP_W - 7, y0, rows * rh - 4, m->ncont, rows, first);

    int can_launch = selected >= 0 && selected < m->ncont &&
                     m->cont[selected].sys_id[0] && m->cont[selected].rom[0];
    const struct dp_hint items[] = {
        { "↑/↓", "Выбор" },
        { "A", can_launch ? "Продолжить" : "Открыть игры" },
        { "X", "Без сейва" },
    };
    dp_hints(cv, items, can_launch ? 3 : 2, NULL);
}

static void dp_screen_systems(struct dp_canvas *cv, const struct dp_model *m, int selected)
{
    char meta[64];
    dp_library_summary(meta, sizeof(meta), m);
    dp_section(cv, "ИГРЫ / СИСТЕМЫ", meta);

    if (m->nsys == 0) {
        dp_empty(cv, m->roms_ok ? "Библиотека пуста" : "Раздел ROMS недоступен",
                 m->roms_ok ? "Скопируйте игры в папки систем на карте" : NULL);
        dp_hints(cv, NULL, 0, "Главная");
        return;
    }

    const int y0 = DP_BODY_Y0 + 2;
    const int rh = 26;
    const int visible_rows = (DP_BODY_Y1 - 6 - y0) / rh;
    const int visible = visible_rows * 2;
    const int first_row = selected / 2 < visible_rows
        ? (selected / 2 > visible_rows - 1 ? selected / 2 - visible_rows + 1 : 0)
        : selected / 2 - visible_rows + 1;
    const int first = first_row * 2;
    const int cw = (DP_W - 2 * DP_PAD - 8) / 2;

    for (int i = first; i < m->nsys && i < first + visible; i++) {
        int col = i % 2;
        int row = (i / 2) - first_row;
        int x = DP_PAD + col * (cw + 8);
        int y = y0 + row * rh;
        dp_row_frame(cv, x, y, cw, rh - 1, i == selected);

        char idu[DP_SYS_ID];
        snprintf(idu, sizeof(idu), "%s", m->systems[i].id);
        for (char *p = idu; *p; p++) {
            if (*p >= 'a' && *p <= 'z')
                *p = (char)(*p - 'a' + 'A');
        }
        char cnt[16];
        snprintf(cnt, sizeof(cnt), "%u", m->systems[i].games);
        int count_x = x + cw - 10 - dp_text_small_w(cnt, 1);
        dp_text_fit(cv, x + 10, y + 6, 46, idu, DP_COL_FG3, 1);
        dp_text_fit(cv, x + 58, y + 4, count_x - x - 68, m->systems[i].name, DP_COL_FG, 0);
        dp_text_small(cv, count_x, y + 6, cnt, DP_COL_FG2, 1);
    }
    dp_scrollbar(cv, DP_W - 7, y0, visible_rows * rh - 2, m->nsys, visible, first);

    const struct dp_hint items[] = {
        { "↑↓←→", "Выбор" },
        { "A", "Открыть" },
        { "L1/R1", "Вкладки" },
    };
    dp_hints(cv, items, 3, "Главная");
}

static void dp_screen_games(struct dp_canvas *cv, const struct dp_model *m, int sys_index,
                            int selected)
{
    if (sys_index < 0 || sys_index >= m->nsys)
        sys_index = 0;
    const struct dp_system *s = m->nsys ? &m->systems[sys_index] : NULL;

    char title[96];
    if (s) {
        snprintf(title, sizeof(title), "ИГРЫ / ");
        size_t used = strlen(title);
        for (const char *p = s->name; *p && used + 1 < sizeof(title); p++, used++)
            title[used] = (char)((*p >= 'a' && *p <= 'z') ? *p - 'a' + 'A' : *p);
        title[used] = '\0';
    } else {
        snprintf(title, sizeof(title), "ИГРЫ / НЕТ СИСТЕМ");
    }

    char meta[64];
    snprintf(meta, sizeof(meta), "%d %s", m->nroms, dp_games_word((unsigned)m->nroms));
    dp_section(cv, title, meta);

    if (!m->nroms) {
        dp_empty(cv, "Игры не найдены", "Папка системы пуста");
        dp_hints(cv, NULL, 0, "Назад");
        return;
    }

    const int y0 = DP_BODY_Y0 + 2;
    const int rh = 34;
    const int rows = (DP_BODY_Y1 - 6 - y0) / rh;
    const int first = dp_first_visible(selected, rows);
    int y = y0;
    for (int i = first; i < m->nroms && i < first + rows; i++) {
        char idx[16];
        snprintf(idx, sizeof(idx), "%d", i + 1);
        int iw = dp_text_small_w(idx, 1);
        dp_row_frame(cv, 8, y, DP_W - 16, rh - 1, i == selected);
        dp_text_small(cv, 20, y + 10, idx, DP_COL_FG3, 1);
        dp_text_fit(cv, 20 + iw + 14, y + 7, DP_W - 70 - iw, m->rom_names[i], DP_COL_FG, 0);
        dp_hline(cv, 20, y + rh - 1, DP_W - 40, DP_COL_LINE);
        y += rh;
    }
    dp_scrollbar(cv, DP_W - 7, y0, rows * rh - 2, m->nroms, rows, first);

    const struct dp_hint items[] = {
        { "↑/↓", "Выбор" },
        { "←/→", "Система" },
        { "A", "Играть" },
    };
    dp_hints(cv, items, 3, "Назад");
}

struct dp_setting_card {
    const char *title;
    char sub[48];
    int editable;
};

static void dp_screen_settings(struct dp_canvas *cv, const struct dp_model *m, int selected)
{
    char meta[32];
    snprintf(meta, sizeof(meta), "%d параметров", 12);
    dp_section(cv, "НАСТРОЙКИ", meta);

    struct dp_setting_card cards[12];
    memset(cards, 0, sizeof(cards));
    cards[0].title = "Регион и язык";
    snprintf(cards[0].sub, sizeof(cards[0].sub), "Русский");
    cards[1].title = "Управление";
    snprintf(cards[1].sub, sizeof(cards[1].sub), "Проверка кнопок");
    cards[2].title = "Дисплей";
    cards[2].editable = 1;
    if (m->cfg_brightness > 0)
        snprintf(cards[2].sub, sizeof(cards[2].sub), "яркость %d%%", m->cfg_brightness);
    else
        snprintf(cards[2].sub, sizeof(cards[2].sub), "не задана");
    cards[3].title = "Звук";
    cards[3].editable = 1;
    if (m->cfg_volume > 0)
        snprintf(cards[3].sub, sizeof(cards[3].sub), "динамик · %d%%", m->cfg_volume);
    else
        snprintf(cards[3].sub, sizeof(cards[3].sub), "не задан");
    cards[4].title = "Сеть";
    snprintf(cards[4].sub, sizeof(cards[4].sub), "USB-модем");
    cards[5].title = "Питание";
    cards[5].editable = 1;
    snprintf(cards[5].sub, sizeof(cards[5].sub), "%s",
             m->cfg_profile[0] ? m->cfg_profile : "не выбран");
    cards[6].title = "Обновления";
    snprintf(cards[6].sub, sizeof(cards[6].sub), "A/B разделы");
    cards[7].title = "Модули";
    snprintf(cards[7].sub, sizeof(cards[7].sub), "%d в списке", m->nmods);
    cards[8].title = "Сведения";
    snprintf(cards[8].sub, sizeof(cards[8].sub), "R36S-V20");
    cards[9].title = "Память";
    snprintf(cards[9].sub, sizeof(cards[9].sub), "%s",
             m->have_sysinfo ? "из /proc/meminfo" : "нет данных");
    cards[10].title = "Файлы и сейвы";
    snprintf(cards[10].sub, sizeof(cards[10].sub), "DATA · ROMS");
    cards[11].title = "Быстро";
    snprintf(cards[11].sub, sizeof(cards[11].sub), "К настройке яркости");

    const int cols = 3, gap = 10;
    const int cw = (DP_W - 2 * DP_PAD - (cols - 1) * gap) / cols;
    const int ch = 82;
    const int y0 = DP_BODY_Y0 + 8;

    for (int i = 0; i < 12; i++) {
        int col = i % cols, row = i / cols;
        int cx = DP_PAD + col * (cw + gap);
        int cy = y0 + row * (ch + 8);
        int sel = i == selected;
        dp_rect(cv, cx, cy, cw, ch, sel ? DP_COL_SEL : DP_COL_PANEL);
        dp_frame(cv, cx, cy, cw, ch, sel ? DP_COL_ACC : DP_COL_LINE);
        if (sel)
            dp_rect(cv, cx + 1, cy + 1, 3, ch - 2, DP_COL_ACC);
        dp_text_fit(cv, cx + 12, cy + 14, cw - 24, cards[i].title, DP_COL_FG, 0);
        dp_text_fit(cv, cx + 12, cy + 42, cw - 24, cards[i].sub, DP_COL_FG2, 1);
        if (cards[i].editable && sel) {
            const char *hint = "A — изменить";
            int hw = dp_text_small_w(hint, 1);
            dp_text_small(cv, cx + cw - 12 - hw, cy + ch - 22, hint, DP_COL_ACC, 1);
        }
    }

    int can_edit = selected == 2 || selected == 3 || selected == 5;
    int can_open = selected == 1 || selected >= 7;
    const struct dp_hint items[] = {
        { "↑↓←→", "Выбор" },
        { "A", can_edit ? "Изменить" : can_open ? "Открыть" : "Просмотр" },
        { "L1/R1", "Вкладки" },
    };
    dp_hints(cv, items, 3, "Главная");
}

static const char *mod_state_label(const char *state)
{
    if (strcmp(state, "ready") == 0)
        return "готов";
    if (strcmp(state, "stopped") == 0)
        return "остановлен";
    if (strcmp(state, "disabled") == 0)
        return "отключён";
    return "неизвестно";
}

static void dp_screen_modules(struct dp_canvas *cv, const struct dp_model *m, int selected)
{
    char meta[32];
    snprintf(meta, sizeof(meta), "%d в списке", m->nmods);
    dp_section(cv, "МОДУЛИ", meta);

    if (!m->nmods) {
        dp_empty(cv, m->modules_online ? "Нет установленных модулей" : "Модули недоступны",
                 m->modules_online ? "Папка /data/modules" : "Проверьте DATA и службу modd");
        dp_hints(cv, NULL, 0, "Главная");
        return;
    }

    const int y0 = DP_BODY_Y0 + 2;
    const int rh = 52;
    const int rows = (DP_BODY_Y1 - 6 - y0) / rh;
    const int first = dp_first_visible(selected, rows);
    int y = y0;
    for (int i = first; i < m->nmods && i < first + rows; i++) {
        const char *state = mod_state_label(m->mods[i].state);
        const char *id = m->mods[i].id;
        const char *name = strcmp(id, "thermal") == 0 ? "Температура и профили" :
                           strcmp(id, "saves") == 0 ? "Резервные копии сейвов" : id;
        uint16_t color = strcmp(m->mods[i].state, "ready") == 0 ? DP_COL_ACC : DP_COL_FG2;
        int right = DP_W - 20 - dp_text_small_w(state, 1);
        dp_row_frame(cv, 8, y, DP_W - 16, rh - 1, i == selected);
        dp_text_fit(cv, 20, y + 15, right - 40, name, DP_COL_FG, 0);
        dp_text_small(cv, right, y + 18, state, color, 1);
        dp_hline(cv, 20, y + rh - 1, DP_W - 40, DP_COL_LINE);
        y += rh;
    }
    const char *id = m->mods[selected].id;
    const struct dp_hint hints[] = {
        { "L1/R1", "Вкладки" },
        { "A", strcmp(id, "saves") == 0 ? "Создать копию" : "Профиль CPU" },
    };
    dp_hints(cv, hints, strcmp(id, "thermal") == 0 || strcmp(id, "saves") == 0 ? 2 : 1, "Назад");
}

static void dp_screen_files(struct dp_canvas *cv, const struct dp_model *m, int selected)
{
    dp_section(cv, "ФАЙЛЫ", NULL);

    char usage[64];
    if (m->rom_total_mb)
        snprintf(usage, sizeof(usage), "%u из %u МиБ занято", m->rom_used_mb, m->rom_total_mb);
    else
        snprintf(usage, sizeof(usage), "%s", m->roms_ok ? "Папка доступна" : "Папка недоступна");
    char library[64];
    dp_library_summary(library, sizeof(library), m);

    const char *rows[][2] = {
        { "DATA", m->data_ok ? "Доступна запись настроек и сейвов" : "Запись недоступна" },
        { "ROMS", usage },
        { "Библиотека", library },
    };

    const int y0 = DP_BODY_Y0 + 2;
    const int n = (int)(sizeof(rows) / sizeof(rows[0]));
    const int rh = 52;
    int y = y0;
    for (int i = 0; i < n; i++) {
        dp_row_frame(cv, 8, y, DP_W - 16, rh - 1, i == selected);
        dp_text(cv, 20, y + 16, rows[i][0], DP_COL_FG, 1);
        dp_text_fit(cv, 168, y + 18, DP_W - 188, rows[i][1], DP_COL_FG2, 1);
        dp_hline(cv, 20, y + rh - 1, DP_W - 40, DP_COL_LINE);
        y += rh;
    }
    dp_hints(cv, NULL, 0, "Главная");
}

static void dp_fmt_uptime(unsigned seconds, char *out, size_t size)
{
    if (seconds < 60)
        snprintf(out, size, "%u с", seconds);
    else if (seconds < 3600)
        snprintf(out, size, "%u мин", seconds / 60);
    else
        snprintf(out, size, "%u ч %02u", seconds / 3600, (seconds / 60) % 60);
}

static void dp_fmt_temp(int mc, char *out, size_t size)
{
    if (mc <= 0)
        snprintf(out, size, "—");
    else
        snprintf(out, size, "%d.%d °C", mc / 1000, (mc % 1000) / 100);
}

static void dp_screen_info(struct dp_canvas *cv, const struct dp_model *m)
{
    dp_section(cv, m->input_test ? "ПРОВЕРКА КОНТРОЛЛЕРА" : "СВЕДЕНИЯ О СИСТЕМЕ",
               m->have_sysinfo ? "Обновление 1 с" : NULL);

    char battery[32], mem[64], temp[24], uptime[24], cpu[64], gpu[32];
    if (m->st.battery >= 0)
        snprintf(battery, sizeof(battery), "%d%%%s", m->st.battery,
                 m->st.charging ? " · зарядка" : "");
    else
        snprintf(battery, sizeof(battery), "нет данных");
    if (m->have_sysinfo && m->si.mem_total_mb)
        snprintf(mem, sizeof(mem), "%u МиБ свободно из %u МиБ",
                 m->si.mem_avail_mb, m->si.mem_total_mb);
    else
        snprintf(mem, sizeof(mem), "—");
    dp_fmt_temp(m->si.temp_mc, temp, sizeof(temp));
    dp_fmt_uptime(m->si.uptime_s, uptime, sizeof(uptime));
    snprintf(cpu, sizeof(cpu), "—");
    snprintf(gpu, sizeof(gpu), "—");
    if (m->si.cpu_khz > 0 && m->si.cpu_max_khz > 0)
        snprintf(cpu, sizeof(cpu), "%ld МГц · предел %ld МГц",
                 m->si.cpu_khz / 1000, m->si.cpu_max_khz / 1000);
    else if (m->si.cpu_khz > 0)
        snprintf(cpu, sizeof(cpu), "%ld МГц", m->si.cpu_khz / 1000);
    if (m->si.gpu_hz > 0)
        snprintf(gpu, sizeof(gpu), "%ld МГц", m->si.gpu_hz / 1000000);

    const char *rows[][2] = {
        { "Частота CPU", cpu },
        { "Частота GPU", gpu },
        { "Температура", temp },
        { "Память", mem },
        { "Батарея", battery },
        { "Профиль CPU", m->cfg_profile[0] ? m->cfg_profile : "не выбран" },
        { "Время работы", m->have_sysinfo ? uptime : "—" },
        { "Экран", m->have_sysinfo && m->si.fb[0] ? m->si.fb : "640x480" },
        { "Ввод", m->have_sysinfo && m->si.input[0] ? m->si.input : "—" },
        { "Последняя кнопка", m->si.last_key[0] ? m->si.last_key : "—" },
        { "Ядро", m->have_sysinfo && m->si.kernel[0] ? m->si.kernel : "—" },
        { "Версия", DP_VERSION " · R36S-V20" },
    };

    const int y0 = DP_BODY_Y0 + 2;
    const int rh = 29;
    const int n = (int)(sizeof(rows) / sizeof(rows[0]));
    int y = y0;
    for (int i = 0; i < n; i++) {
        dp_text(cv, 20, y + 6, rows[i][0], DP_COL_FG2, 1);
        dp_text_fit(cv, 202, y + 6, DP_W - 222, rows[i][1], DP_COL_FG, 0);
        dp_hline(cv, 20, y + rh - 1, DP_W - 40, DP_COL_LINE);
        y += rh;
    }
    if (m->input_test) {
        const struct dp_hint hints[] = { { "B", "Два нажатия для возврата" } };
        dp_hints(cv, hints, 1, NULL);
        return;
    }
    const struct dp_hint hints[] = { { "L1/R1", "Вкладки" } };
    dp_hints(cv, hints, 1, "Назад");
}

/* ------------------------------------------------------------- overlays */

void dp_ui_toast(struct dp_canvas *cv, const char *message)
{
    if (!message || !message[0])
        return;
    int tw = dp_text_small_w(message, 1);
    int w = tw + 32;
    if (w > DP_W - 40)
        w = DP_W - 40;
    int x = (DP_W - w) / 2;
    int y = DP_BODY_Y1 - 44;
    dp_rect(cv, x, y, w, 32, DP_COL_PANEL2);
    dp_frame(cv, x, y, w, 32, DP_COL_WARN);
    dp_text_fit(cv, x + 16, y + 9, w - 32, message, DP_COL_FG, 1);
}

void dp_ui_overlay(struct dp_canvas *cv, const char *title, const char *line1,
                   const char *line2, int done, int total)
{
    const int w = 460, h = 176;
    const int x = (DP_W - w) / 2, y = (DP_H - h) / 2;
    dp_rect(cv, x, y, w, h, DP_COL_PANEL2);
    dp_frame(cv, x, y, w, h, DP_COL_ACC);
    dp_text_fit(cv, x + 20, y + 18, w - 40, title, DP_COL_FG, 0);
    if (line1)
        dp_text_fit(cv, x + 20, y + 56, w - 40, line1, DP_COL_FG2, 1);
    if (line2)
        dp_text_fit(cv, x + 20, y + 80, w - 40, line2, DP_COL_FG2, 1);
    if (total > 0) {
        int bw = w - 40, fill = bw * (done > total ? total : done) / total;
        dp_rect(cv, x + 20, y + h - 42, bw, 10, DP_COL_PANEL);
        dp_rect(cv, x + 20, y + h - 42, fill, 10, DP_COL_ACC);
        char counter[24];
        snprintf(counter, sizeof(counter), "%d / %d", done, total);
        int cw = dp_text_small_w(counter, 1);
        dp_text_small(cv, x + w - 20 - cw, y + h - 26, counter, DP_COL_FG3, 1);
    }
}

void dp_ui_paint(struct dp_canvas *cv, const struct dp_model *m, enum dp_screen scr,
                 int system_index, int selected)
{
    dp_fill(cv, DP_COL_BG);
    dp_statusbar(cv, m, scr);

    switch (scr) {
    case DP_SCR_CONTINUE: dp_screen_continue(cv, m, selected); break;
    case DP_SCR_SYSTEMS: dp_screen_systems(cv, m, selected); break;
    case DP_SCR_GAMES: dp_screen_games(cv, m, system_index, selected); break;
    case DP_SCR_SETTINGS: dp_screen_settings(cv, m, selected); break;
    case DP_SCR_MODULES: dp_screen_modules(cv, m, selected); break;
    case DP_SCR_FILES: dp_screen_files(cv, m, selected); break;
    case DP_SCR_INFO: dp_screen_info(cv, m); break;
    default: break;
    }
}

void dp_ui_boot_splash(struct dp_canvas *cv)
{
    static const char wordmark[] = "DEEPoS";
    static const char status[] = "Загрузка системы";
    dp_fill(cv, DP_COL_BG);
    dp_frame(cv, 16, 16, DP_W - 32, DP_H - 32, DP_COL_LINE);
    dp_hline(cv, 16, 16, 28, DP_COL_ACC);
    dp_vline(cv, 16, 16, 24, DP_COL_ACC);
    dp_hline(cv, DP_W - 44, DP_H - 17, 28, DP_COL_ACC);
    dp_vline(cv, DP_W - 17, DP_H - 40, 24, DP_COL_ACC);

    int x = (DP_W - dp_text_w(wordmark, 5)) / 2;
    dp_text(cv, x, 174, wordmark, DP_COL_ACC, 5);
    dp_hline(cv, x, 263, DP_W - 2 * x, DP_COL_LINE);
    x = (DP_W - dp_text_w(status, 1)) / 2;
    dp_text(cv, x, 280, status, DP_COL_FG2, 1);
}
