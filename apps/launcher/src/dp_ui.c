#include "dp_ui.h"

#include <stdio.h>
#include <string.h>

#include "dp_theme.h"

#define DP_TABS 6

static const char *const dp_tabs[DP_TABS] = {
    "ПРОДОЛЖИТЬ", "ИГРЫ", "НАСТРОЙКИ", "МОДУЛИ", "ФАЙЛЫ", "СВЕДЕНИЯ",
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

static void dp_key(struct dp_canvas *cv, int x, int y, const char *label)
{
    int w = dp_text_small_w(label, 1) + 8;
    dp_rect(cv, x, y, w, 15, DP_COL_PANEL2);
    dp_frame(cv, x, y, w, 15, DP_COL_LINE);
    dp_text_small(cv, x + 4, y + 4, label, DP_COL_FG2, 1);
}

static int dp_hint(struct dp_canvas *cv, int x, int y, const char *key, const char *label)
{
    dp_key(cv, x, y, key);
    int kw = dp_text_small_w(key, 1) + 8;
    return kw + 8 + dp_text_small(cv, x + kw + 8, y + 4, label, DP_COL_FG2, 1) + 18;
}

static void dp_hint_right(struct dp_canvas *cv, const char *key, const char *label)
{
    int kw = dp_text_small_w(key, 1) + 8;
    int tw = kw + 8 + dp_text_small_w(label, 1) + 14;
    int x = DP_W - tw;
    dp_key(cv, x, DP_H - DP_HINT_H + 6, key);
    dp_text_small(cv, x + kw + 8, DP_H - DP_HINT_H + 10, label, DP_COL_FG2, 1);
}

static void dp_statusbar(struct dp_canvas *cv, const struct dp_model *m, enum dp_screen active)
{
    dp_rect(cv, 0, 0, DP_W, DP_STATUS_H, DP_COL_PANEL);

    int cur = dp_tab_index(active);
    int x = 12;
    for (int i = 0; i < DP_TABS; i++) {
        int tw = dp_text_small_w(dp_tabs[i], 1);
        uint16_t col = (i == cur) ? DP_COL_FG : DP_COL_FG3;
        dp_text_small(cv, x, 11, dp_tabs[i], col, 1);
        if (i == cur)
            dp_rect(cv, x, DP_STATUS_H - 3, tw, 2, DP_COL_ACC);
        x += tw + 10;
    }

    char buf[16];
    snprintf(buf, sizeof(buf), "%s", m->st.clock[0] ? m->st.clock : "00:00");
    int cw = dp_text_small_w(buf, 1);
    dp_text_small(cv, DP_W - 12 - cw, 11, buf, DP_COL_FG2, 1);

    int bx = DP_W - 12 - cw - 10 - 24;
    dp_frame(cv, bx, 11, 24, 11, DP_COL_FG3);
    dp_rect(cv, bx + 1, 12, 22, 9, DP_COL_BG);
    int fill = 22 * (m->st.battery < 0 ? 0 : m->st.battery) / 100;
    dp_rect(cv, bx + 1, 12, fill, 9, m->st.battery <= 20 ? DP_COL_BAD : DP_COL_ACC);
    if (m->st.charging) {
        dp_rect(cv, bx + 9, 13, 2, 7, DP_COL_WARN);
        dp_rect(cv, bx + 12, 13, 2, 4, DP_COL_WARN);
    }

    snprintf(buf, sizeof(buf), "%d%%", m->st.battery < 0 ? 0 : m->st.battery);
    int pw = dp_text_small_w(buf, 1);
    dp_text_small(cv, bx - 7 - pw, 11, buf, DP_COL_FG2, 1);
}

static void dp_section(struct dp_canvas *cv, const char *title, const char *meta)
{
    int y = DP_STATUS_H;
    dp_rect(cv, 0, y, DP_W, DP_HEADER_H, DP_COL_BG);
    dp_text_small(cv, 12, y + 9, title, DP_COL_FG2, 1);
    if (meta) {
        int mw = dp_text_small_w(meta, 1);
        dp_text_small(cv, DP_W - 12 - mw, y + 9, meta, DP_COL_FG3, 1);
    }
    dp_hline(cv, 0, y + DP_HEADER_H - 1, DP_W, DP_COL_LINE);
}

static void dp_hintbar(struct dp_canvas *cv, const char *keys[], const char *labels[], int n,
                       const char *back_key, const char *back_label)
{
    int y = DP_H - DP_HINT_H;
    dp_rect(cv, 0, y, DP_W, DP_HINT_H, DP_COL_PANEL);
    dp_hline(cv, 0, y, DP_W, DP_COL_LINE);
    int x = 12;
    for (int i = 0; i < n; i++)
        x += dp_hint(cv, x, y + 6, keys[i], labels[i]);
    if (back_label)
        dp_hint_right(cv, back_key, back_label);
}

static void dp_row_frame(struct dp_canvas *cv, int y, int h, int selected)
{
    if (selected) {
        dp_rect(cv, 8, y, DP_W - 16, h - 1, DP_COL_SEL);
        dp_rect(cv, 8, y, 2, h - 1, DP_COL_ACC);
    }
}

static void dp_initials(const char *title, char *out, size_t n)
{
    size_t k = 0;
    int word = 0;
    for (const char *p = title; *p && k + 1 < n && word < 2; p++) {
        unsigned char c = (unsigned char)*p;
        if (c < 0x80 && (c == ' ' || c == ':' || c == '-')) {
            word++;
            continue;
        }
        if ((size_t)word == k) {
            if (c >= 'a' && c <= 'z')
                c = (unsigned char)(c - 'a' + 'A');
            out[k++] = (char)c;
            word++;
        }
    }
    out[k] = '\0';
    if (k == 0)
        snprintf(out, n, "--");
}

/* ---------------------------------------------------------------- screens */

static void dp_screen_continue(struct dp_canvas *cv, const struct dp_model *m)
{
    char meta[48];
    snprintf(meta, sizeof(meta), "%d игр", m->ncont);
    dp_section(cv, "ПРОДОЛЖИТЬ", meta);

    int y = DP_STATUS_H + DP_HEADER_H;
    for (int i = 0; i < m->ncont; i++) {
        const struct dp_continue_item *it = &m->cont[i];
        int rh = 36;
        if (y + rh > DP_H - DP_HINT_H)
            break;
        dp_row_frame(cv, y, rh, i == 0);

        char ini[4];
        dp_initials(it->title, ini, sizeof(ini));
        dp_rect(cv, 20, y + 4, 34, 27, DP_COL_PANEL2);
        int iw = dp_text_w(ini, 1);
        dp_text(cv, 20 + (34 - iw) / 2, y + 11, ini, DP_COL_ACC, 1);

        int tx = 66;
        dp_text(cv, tx, y + 6, it->title, DP_COL_FG, 1);
        int tw = dp_text_w(it->title, 1);
        dp_text_small(cv, tx + tw + 12, y + 12, it->system, DP_COL_FG3, 1);

        int mw = dp_text_small_w(it->meta, 1);
        int mx = DP_W - 16 - mw;
        dp_text_small(cv, mx, y + 12, it->meta, DP_COL_FG2, 1);

        if (it->has_save) {
            char badge[20];
            if (it->slot >= 0)
                snprintf(badge, sizeof(badge), "СЛОТ %d", it->slot);
            else
                snprintf(badge, sizeof(badge), "АВТОСЕЙВ");
            int bw = dp_text_small_w(badge, 1) + 10;
            int bx = mx - 12 - bw;
            dp_frame(cv, bx, y + 9, bw, 16, DP_COL_LINE);
            dp_text_small(cv, bx + 5, y + 13, badge, DP_COL_FG2, 1);
        }
        y += rh;
    }

    if (m->ncont == 0) {
        int y0 = DP_STATUS_H + DP_HEADER_H;
        int cy = y0 + 70;
        const char *h1 = "Нет недавних игр";
        dp_text_small(cv, (DP_W - dp_text_small_w(h1, 1)) / 2, cy, h1, DP_COL_ACC, 1);
        const char *h2 = "Запущенная игра появится здесь";
        dp_text(cv, (DP_W - dp_text_w(h2, 1)) / 2, cy + 30, h2, DP_COL_FG2, 1);
    }

    static const char *keys[] = { "A", "X", "SEL" };
    static const char *labels[] = { "Продолжить", "Без сейва", "Слот" };
    dp_hintbar(cv, keys, labels, 3, "B", "Назад");
}

static const char *dp_games_word(unsigned n)
{
    unsigned m100 = n % 100, m10 = n % 10;
    if (m100 >= 11 && m100 <= 14)
        return "игр";
    if (m10 == 1)
        return "игра";
    if (m10 >= 2 && m10 <= 4)
        return "игры";
    return "игр";
}

static void dp_screen_systems(struct dp_canvas *cv, const struct dp_model *m)
{
    char meta[64];
    snprintf(meta, sizeof(meta), "%d систем · %u %s", m->nsys, m->total_games,
             dp_games_word(m->total_games));
    dp_section(cv, "ИГРЫ / СИСТЕМЫ", meta);

    int y0 = DP_STATUS_H + DP_HEADER_H;
    int rh = 24;
    int rows = (DP_H - DP_HINT_H - y0) / rh;
    int half = (m->nsys + 1) / 2;
    if (half > rows)
        half = rows;

    for (int i = 0; i < m->nsys && i < half * 2; i++) {
        int col = i / half;
        int row = i % half;
        int x = col == 0 ? 8 : 324;
        int y = y0 + row * rh;
        if (col == 0)
            dp_row_frame(cv, y, rh, i == 0);

        char idu[8];
        snprintf(idu, sizeof(idu), "%s", m->systems[i].id);
        for (char *p = idu; *p; p++) {
            if (*p >= 'a' && *p <= 'z')
                *p = (char)(*p - 'a' + 'A');
        }
        dp_text_small(cv, x + 8, y + 8, idu, DP_COL_FG3, 1);
        dp_text(cv, x + 46, y + 4, m->systems[i].name, DP_COL_FG, 1);

        char cnt[16];
        snprintf(cnt, sizeof(cnt), "%u", m->systems[i].games);
        int cw = dp_text_small_w(cnt, 1);
        dp_text_small(cv, x + 300 - cw, y + 8, cnt, DP_COL_FG2, 1);
    }

    if (m->nsys == 0) {
        /* Fresh card: explain how to fill the library instead of a blank page. */
        static const char *hint[3] = {
            "Библиотека пуста",
            "Скопируйте папки систем на карту",
            "ROM-раздел виден с ПК по USB",
        };
        int cy = y0 + 90;
        for (int i = 0; i < 3; i++) {
            int w = (i == 0) ? dp_text_small_w(hint[i], 1) : dp_text_w(hint[i], 1);
            if (i == 0)
                dp_text_small(cv, (DP_W - w) / 2, cy, hint[i], DP_COL_ACC, 1);
            else
                dp_text(cv, (DP_W - w) / 2, cy + i * 30, hint[i], DP_COL_FG2, 1);
        }
    }

    static const char *keys[] = { "A", "Y" };
    static const char *labels[] = { "Открыть", "Фильтр" };
    dp_hintbar(cv, keys, labels, 2, "B", "Назад");
}

static void dp_screen_games(struct dp_canvas *cv, const struct dp_model *m, int sys_index)
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
    snprintf(meta, sizeof(meta), "%u игр · A–Z", s ? s->games : 0u);
    dp_section(cv, title, meta);

    int y = DP_STATUS_H + DP_HEADER_H;
    int rh = 32;
    int rows = (DP_H - DP_HINT_H - y) / rh;
    for (int i = 0; i < rows; i++) {
        dp_row_frame(cv, y, rh, i == 1);
        dp_rect(cv, 20, y + 6, 24, 19, DP_COL_PANEL2);
        dp_text_small(cv, 26, y + 11, "?", DP_COL_FG3, 1);

        char name[24];
        if (s)
            snprintf(name, sizeof(name), "игра %02d", i + 1);
        else
            snprintf(name, sizeof(name), "—");
        dp_text(cv, 56, y + 6, name, DP_COL_FG, 1);
        if (s)
            dp_text_small(cv, 56 + dp_text_w(name, 1) + 10, y + 12, s->id, DP_COL_FG3, 1);
        dp_text_small(cv, DP_W - 16 - dp_text_small_w("—", 1), y + 12, "—", DP_COL_FG3, 1);
        y += rh;
    }

    static const char *keys[] = { "A", "Y", "X", "SEL" };
    static const char *labels[] = { "Играть", "Буква", "Избранное", "Опции" };
    dp_hintbar(cv, keys, labels, 4, "B", "Назад");
}

struct dp_setting_card {
    const char *title;
    const char *sub;
};

static void dp_screen_settings(struct dp_canvas *cv, const struct dp_model *m)
{
    dp_section(cv, "НАСТРОЙКИ", "импорт с Arch-R: 24 из 24");

    char sub_display[48];
    char sub_sound[48];
    char sub_power[48];
    if (m->cfg_brightness > 0)
        snprintf(sub_display, sizeof(sub_display), "яркость %d%%", m->cfg_brightness);
    else
        snprintf(sub_display, sizeof(sub_display), "не задана");
    if (m->cfg_volume > 0)
        snprintf(sub_sound, sizeof(sub_sound), "динамик · %d%%", m->cfg_volume);
    else
        snprintf(sub_sound, sizeof(sub_sound), "не задан");
    snprintf(sub_power, sizeof(sub_power), "%s · CPU",
             m->cfg_profile[0] ? m->cfg_profile : "авто");

    const struct dp_setting_card cards[] = {
        { "Регион и язык", "Русский · UTC+5" },
        { "Управление", "A/B исправлены" },
        { "Дисплей", sub_display },
        { "Звук", sub_sound },
        { "Сеть", "USB-сеть · SSH вкл" },
        { "Питание", sub_power },
        { "Обновления", "stable · 20261116" },
        { "Модули", "4 включено" },
        { "Сведения", "SoC 48 °C · RAM 212 МБ" },
        { "Память", "zram 1.5 ГБ · lz4" },
        { "Файлы и сейвы", "бэкап сегодня" },
        { "Быстро", "сон · перезагрузка" },
    };
    const int n = (int)(sizeof(cards) / sizeof(cards[0]));
    const int cols = 3, cw = 200, ch = 82, gap = 6;
    int x0 = 12, y0 = DP_STATUS_H + DP_HEADER_H + 6;

    for (int i = 0; i < n; i++) {
        int cx = x0 + (i % cols) * (cw + gap);
        int cy = y0 + (i / cols) * (ch + gap);
        if (cy + ch > DP_H - DP_HINT_H)
            break;
        dp_rect(cv, cx, cy, cw, ch, DP_COL_PANEL);
        dp_frame(cv, cx, cy, cw, ch, i == 0 ? DP_COL_ACC : DP_COL_LINE);
        dp_text(cv, cx + 12, cy + 48, cards[i].title, DP_COL_FG, 1);
        dp_text_small(cv, cx + 12, cy + 66, cards[i].sub, DP_COL_FG2, 1);
        dp_rect(cv, cx + cw - 24, cy + 12, 10, 10, DP_COL_PANEL2);
        dp_frame(cv, cx + cw - 24, cy + 12, 10, 10, DP_COL_FG3);
    }
    (void)m;

    static const char *keys[] = { "A", "Y" };
    static const char *labels[] = { "Изменить", "Сброс раздела" };
    dp_hintbar(cv, keys, labels, 2, "B", "Назад");
}

struct dp_module_row {
    const char *name;
    const char *sub;
    int enabled;
};

static void dp_toggle(struct dp_canvas *cv, int x, int y, int on)
{
    dp_rect(cv, x, y, 34, 18, on ? DP_COL_ACC : DP_COL_PANEL2);
    dp_frame(cv, x, y, 34, 18, on ? DP_COL_ACC : DP_COL_LINE);
    int kx = on ? x + 18 : x + 2;
    dp_rect(cv, kx, y + 2, 14, 14, on ? DP_COL_BG : DP_COL_FG3);
}

static const char *mod_state_label(const char *state)
{
    if (strcmp(state, "ready") == 0)
        return "включён · отвечает на запросы";
    if (strcmp(state, "stopped") == 0)
        return "остановлен · запустится при действии";
    if (strcmp(state, "disabled") == 0)
        return "отключён · три падения за 10 минут";
    return "состояние неизвестно";
}

static void dp_screen_modules(struct dp_canvas *cv, const struct dp_model *m)
{
    char meta[64];
    if (m->nmods > 0) {
        int on = 0;
        for (int i = 0; i < m->nmods; i++)
            if (strcmp(m->mods[i].state, "ready") == 0)
                on++;
        snprintf(meta, sizeof(meta), "modd · %d модулей · %d активных", m->nmods, on);
    } else {
        snprintf(meta, sizeof(meta), "%s", "modd не запущен · демо-данные");
    }
    dp_section(cv, "МОДУЛИ", meta);

    static const struct dp_module_row rows[] = {
        { "Температура и профили", "тайл в «Продолжить» · права: cpu-profile, brightness", 1 },
        { "Бэкап сейвов", "ежедневно 04:00 · 10 архивов · права: roms", 1 },
        { "Автонастройка ЦП", "подбор частоты под игру · права: cpu-tune", 1 },
        { "Батарея подробно", "напряжение, ток, износ · права: нет", 1 },
        { "itch.io каталог", "нужен интернет · права: net", 0 },
    };

    int y = DP_STATUS_H + DP_HEADER_H;
    if (m->nmods > 0) {
        for (int i = 0; i < m->nmods && i < 6; i++) {
            int rh = 46;
            dp_row_frame(cv, y, rh, i == 0);
            dp_text(cv, 20, y + 8, m->mods[i].id, DP_COL_FG, 1);
            dp_text_small(cv, 20, y + 26, mod_state_label(m->mods[i].state), DP_COL_FG3, 1);
            dp_toggle(cv, DP_W - 20 - 34, y + 14, strcmp(m->mods[i].state, "ready") == 0);
            y += rh;
        }
    } else {
        int n = (int)(sizeof(rows) / sizeof(rows[0]));
        for (int i = 0; i < n; i++) {
            int rh = 46;
            dp_row_frame(cv, y, rh, i == 0);
            dp_text(cv, 20, y + 8, rows[i].name, DP_COL_FG, 1);
            dp_text_small(cv, 20, y + 26, rows[i].sub, DP_COL_FG3, 1);
            dp_toggle(cv, DP_W - 20 - 34, y + 14, rows[i].enabled);
            y += rh;
        }
    }

    dp_hline(cv, 20, y + 6, DP_W - 40, DP_COL_LINE);
    dp_text(cv, 20, y + 16, "Найти ещё модули", DP_COL_FG, 1);
    dp_text_small(cv, 20 + dp_text_w("Найти ещё модули", 1) + 12, y + 20,
                  "магазин · 12 доступно", DP_COL_FG3, 1);
    int ow = dp_text_small_w("открыть", 1);
    dp_text_small(cv, DP_W - 20 - ow, y + 20, "открыть", DP_COL_ACC, 1);

    static const char *keys[] = { "A", "Y" };
    static const char *labels[] = { "Вкл/выкл", "Права" };
    dp_hintbar(cv, keys, labels, 2, "B", "Назад");
}

static void dp_screen_files(struct dp_canvas *cv, const struct dp_model *m)
{
    dp_section(cv, "ФАЙЛЫ И ПЕРЕДАЧА", "USB подключён");

    char romline[80];
    snprintf(romline, sizeof(romline), "%u / %u ГБ занято · %d систем", m->rom_used_mb,
             m->rom_total_mb, m->nsys);

    struct {
        const char *label;
        const char *sub;
        const char *action;
        uint16_t action_col;
    } rows[] = {
        { "Режим USB", "сеть (NCM) · SSH и Samba доступны с ПК", "сеть", DP_COL_ACC },
        { "Передача файлов", "MTP: на ПК появится «R36S» и папка ROMS", "переключить", DP_COL_FG2 },
        { "Сейвы", "последний бэкап 14:22 · 135 Б · 0 файлов", "сделать копию", DP_COL_ACC },
        { "ROM'ы", romline, "28.6 ГБ свободно", DP_COL_FG2 },
        { "Обновления системы", "stable · установлено 20261116 · проверить", "актуально", DP_COL_FG2 },
        { "Бэкап загрузчика", "снимок первых 512 МиБ карты на ПК", "сделать", DP_COL_FG2 },
    };

    int y = DP_STATUS_H + DP_HEADER_H;
    int n = (int)(sizeof(rows) / sizeof(rows[0]));
    for (int i = 0; i < n; i++) {
        int rh = 46;
        dp_row_frame(cv, y, rh, i == 0);
        dp_text(cv, 20, y + 8, rows[i].label, DP_COL_FG, 1);
        dp_text_small(cv, 20, y + 26, rows[i].sub, DP_COL_FG3, 1);
        int aw = dp_text_small_w(rows[i].action, 1);
        dp_text_small(cv, DP_W - 20 - aw, y + 16, rows[i].action, rows[i].action_col, 1);
        y += rh;
    }

    static const char *keys[] = { "A" };
    static const char *labels[] = { "Выполнить" };
    dp_hintbar(cv, keys, labels, 1, "B", "Назад");
}

static void dp_screen_info(struct dp_canvas *cv, const struct dp_model *m)
{
    dp_section(cv, "СВЕДЕНИЯ О СИСТЕМЕ", "r36s-clone · плата R36S-V20");

    char battery[24], ram[32], games[40], stor[32];
    snprintf(battery, sizeof(battery), "%d%%", m->st.battery);
    snprintf(ram, sizeof(ram), "%d / 732 МБ", 212);
    snprintf(games, sizeof(games), "%d систем", m->nsys);
    snprintf(stor, sizeof(stor), "%u / %u ГБ", m->rom_used_mb, m->rom_total_mb);

    const char *left[][2] = {
        { "Система", "DEEPoS 0.1" },
        { "Ядро", "6.12 LTS" },
        { "CPU", "1416 МГц · ondemand" },
        { "GPU", "650 МГц" },
        { "SoC", "48 °C" },
        { "GPU темп.", "51 °C" },
        { "ОЗУ", ram },
        { "zram", "1.5 ГБ · lz4" },
    };
    const char *right[][2] = {
        { "Батарея", battery },
        { "Питание", "разряд · 3.99 В" },
        { "Износ", "87.5%" },
        { "Карта", stor },
        { "Разделы", "A/B · DATA · ROMS" },
        { "Библиотека", games },
        { "В работе", "2 ч 14 мин" },
        { "Обновления", "20261116 · stable" },
    };

    int y = DP_STATUS_H + DP_HEADER_H + 10;
    int rh = 26;
    for (int i = 0; i < 8; i++) {
        int yy = y + i * rh;
        dp_text_small(cv, 12, yy + 6, left[i][0], DP_COL_FG3, 1);
        dp_text_small(cv, 112, yy + 4, left[i][1], DP_COL_FG, 1);
        dp_hline(cv, 12, yy + rh - 2, 300, DP_COL_LINE);

        dp_text_small(cv, 332, yy + 6, right[i][0], DP_COL_FG3, 1);
        dp_text_small(cv, 462, yy + 4, right[i][1], DP_COL_FG, 1);
        dp_hline(cv, 332, yy + rh - 2, 296, DP_COL_LINE);
    }

    static const char *keys[] = { "Y", "X" };
    static const char *labels[] = { "Скопировать отчёт", "Полный лог" };
    dp_hintbar(cv, keys, labels, 2, "B", "Назад");
}

void dp_ui_paint(struct dp_canvas *cv, const struct dp_model *m, enum dp_screen scr,
                 int system_index, int selected)
{
    (void)selected;
    dp_fill(cv, DP_COL_BG);
    dp_statusbar(cv, m, scr);

    switch (scr) {
    case DP_SCR_CONTINUE: dp_screen_continue(cv, m); break;
    case DP_SCR_SYSTEMS: dp_screen_systems(cv, m); break;
    case DP_SCR_GAMES: dp_screen_games(cv, m, system_index); break;
    case DP_SCR_SETTINGS: dp_screen_settings(cv, m); break;
    case DP_SCR_MODULES: dp_screen_modules(cv, m); break;
    case DP_SCR_FILES: dp_screen_files(cv, m); break;
    case DP_SCR_INFO: dp_screen_info(cv, m); break;
    default: break;
    }
}
