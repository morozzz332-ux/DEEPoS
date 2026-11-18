# Журнал работ DEEPoS

Формат записи: `YYYY-MM-DD · этап · что сделано · что сломалось · следующий шаг`.

## 2026-11-18 · P0 (подготовка)

- Собран публичный репозиторий: спецификация, брендинг, макеты UI, практические инструкции.
- Прошивка Arch-R на устройстве изучена как baseline: ядро 6.12.114, 1 ГБ ОЗУ, панель ST7703.
- Следующий шаг: bootstrap-образ — загрузчик/DDR-init из Arch-R clone, свой `KERNEL`, DTB и
  `extlinux.conf`; снять UART-лог загрузки (115200), записать в этот файл.

## 2026-11-18 · P4a (лаунчер, host-прототип)

Сделано:

- `tools/gen-font.py` — генератор битмап-шрифтов из `tools/fonts/DejaVuSansMono.ttf`
  (permissive, DejaVu 2.37). Два размера: 13 px (advance 8, box 17) и 11 px (advance 7, box 14),
  181 глиф: ASCII, кириллица, «Ёё«»—–·…№°×→←↑↓▲▼◆●○■□».
- `apps/launcher` — C11, без внешних зависимостей: `dp_canvas` (RGB565-буфер, примитивы,
  UTF-8-декодер, текст), `dp_theme` (токены палитры), `dp_model`/`dp_scan` (сканер ROM-разделов,
  таблица 160 систем, расширения по системам), `dp_ui` (6 экранов: Продолжить / Игры /
  Настройки / Модули / Файлы / Сведения), `main` (CLI: `--roms --data --screen --out FILE.ppm`,
  `--system --battery --charging --clock --rom-used --rom-total --list --list-roms --help`).
- `tests/ci/Dockerfile` → образ `deepos-build:local` (alpine 3.20 + build-base + py3-pillow);
  `tests/ci/render-all.sh` — фикстуры (1 901 файл ROM в 12 системах) и рендер 7 экранов в PPM.
- `tests/run.py` — сборка, рендер каждого экрана, проверки: размер 640×480, палитра (все цвета
  должны быть токенами темы, усечёнными до RGB565), непустой статус-бар и тело, детерминизм
  байтов PPM, golden-хэши (`tests/golden/hashes.json`), `--list` (6 экранов), `--list-roms`
  (12 систем, `md 312`, `snes 286`), `--help`, отказ на неизвестном `--screen`.
- `Makefile` (fonts/launcher/render/test/docker-image/docker-test), CI-workflow
  `.github/workflows/ci.yml` (проверка актуальности шрифтов, тесты, секрет-сканер).

Что сломалось и как починено:

- Первые шрифты были 12×12 с 13 px кеглем — нижние ряды обрезались, кириллица не читалась;
  перешли на раздельные advance/box из метрик PIL (`ascent+descent`), 13/17 и 11/14.
- Генератор сначала писал биты LSB-first, а `dp_canvas` читает MSB-first — текст выходил
  зеркальным; исправлено на `1 << (advance - 1 - x)`.
- Тест падал на «цвета вне палитры» из-за двух багов самого теста: PPM-парсер не отрезал
  строку `255`, а палитра парсилась как `0xRRGGBB`, тогда как в `dp_theme.h` это
  `dp565(r, g, b)`. После починки — 0 неизвестных цветов.
- Segfault на старте: `dp_tabs[DP_SCR_COUNT]` содержал 7 слотов при 6 вкладках (последний
  NULL, цикл до `DP_SCR_COUNT`); введены `DP_TABS 6` и `dp_tab_index()`.

Следующий шаг: `apps/modd` (супервизор модулей + JSON-RPC-транспорт с тестовым лаунчером),
`apps/saved` (сейвы и resume), перенос модулей `thermal`/`saves` в `modules/` с юнит-тестами,
затем `board/r36s-v20` и `tools/flash.ps1`.