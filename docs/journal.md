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
## 2026-11-18 · P4b (modd, супервизор модулей)

Сделано:

- `apps/modd` — C11, без зависимостей: `dp_json` (минимальные хелперы разбора/экранирования),
  `dp_module` (манифест `module.toml`, spawn через `/bin/sh -c`, NDJSON-транспорт с id-матчингом,
  таймауты, SIGTERM→SIGKILL, учёт падений), `modd` (UNIX-сокет `--socket`, методы `status`,
  `initialize`, `action.invoke`, `shutdown`; ре-ап при необходимости, лог в stderr).
- Протокол совместим по форме с Arch-R modules api 3: `{"jsonrpc":"2.0","id":N,"method":…,"params":…}`,
  ответы `{"id":N,"result":…}` / `{"id":N,"error":{…}}`; модулю выставляются `MODD_MODULE_DATA`
  и `ARCHR_MODULE_DATA` (каталог `--data/<id>`, 0700).
- Наблюдатель: 3 падения за 10 минут → `disabled`; таймауты по умолчанию 10 000 мс на
  `initialize` и 1 000 мс на `action.invoke`, переопределяются `MODD_INIT_MS` / `MODD_ACTION_MS`
  (в тестах 400/300 мс).
- `tests/fixtures/modd/{thermal,hang,crash}` — модули-заглушки: рабочий, «молчащий» и падающий.
- `tests/modd_test.py` — гоняет modd по сокету: `status` (три модуля), `initialize`,
  два `action.invoke` (`eco`, `balanced`) с проверкой файла действий, неизвестный модуль,
  таймаут «молчащего» (<3 с при бюджете 0.4 с), watchdog (3 падения → `disabled`), `shutdown`.
- `Makefile`: цели `modd`, `modd-test`, `docker-test` теперь гоняет оба набора; CI — отдельный шаг.

Что сломалось и как починено:

- musl/Alpine со `-std=c11 -Werror` не видел `setenv/kill/nanosleep` — добавлены
  `-D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L`; удалена неиспользуемая переменная `deadline`.

Метрики: бинарь modd 33 152 B, `tests/modd_test.py` ~0.64 с, профиль ОЗУ модуля — по манифесту
(`memory_mb`), реальный cgroup-учёт появится на этапе сборки образа (systemd-run).
## 2026-11-18 · P4c (saved, атомарное хранилище сейвов)

Сделано:

- `apps/saved` — C11-утилита поверх каталога `--data`: `put`, `get`, `last`, `list`, `clean`,
  `recover`. Раскладка `saves/<system>/<rom-key>/slot<N>.state` + `slot<N>.json`
  (`{"slot","size","ts"}`) + `last` (последний слот игрока) + журнал `saves/.journal`.
- Атомарность: запись идёт в `slot<N>.state.tmp`, затем `fsync`, `rename`, `fsync` каталога
  (`copy_atomic`/`write_meta`). Метаданные пишутся тем же приёмом. При обрыве питания на диске
  остаётся либо старый, либо новый слот, но не «половина».
- Журнал: `BEGIN <path>` перед записью, `COMMIT <path>` после; `saved recover` удаляет `.tmp`
  у записей без `COMMIT` и очищает журнал (идемпотентно, вызывается при старте).
- `clean` подчищает хвосты `.tmp` для state и meta.
- Коды возврата: 0 — успех, 2 — ошибка ввода-вывода, 3 — неверные аргументы (слот вне 0..4),
  4 — файл/слот не найден.

Тесты (`tests/saved_test.py`, 146 мс): put/get с проверкой пути и меты, `last` = последний
записанный слот, `list` с размерами, перезапись слота без временных файлов, ошибки 3/4,
`recover` (подложен `.tmp` + `BEGIN` без `COMMIT` — временный файл удалён, ранее сохранённый
слот цел), `clean` для state/meta.

Найдено тестом и исправлено: `journal_add` создавал каталог `.journal` (журнал должен быть
файлом) — теперь создаётся только каталог `saves/`, а файл открывается на дозапись.

Метрики: бинарь `saved` 23 736 B, тесты 0.146 с.
## 2026-11-18 · P4b+ (modules: thermal и saves, api 3)

Перенесены два первых модуля в `modules/` и покрыты host-тестами (`tests/modules_test.py`).

- `modules/thermal` — тайл `temps` + страница `main`; читает `/sys/class/thermal/*`, `cpufreq policy0`, `devfreq ff400000.gpu`; действия `eco|balanced|max` только пишут файл-запрос в `MODD_MODULE_DATA`, привилегированное применение делает `root/thermal-apply.sh` (запускается root-юнитом на устройстве, в тестах — вручную с `SYSFS_PREFIX`).
- `modules/saves` — тайл `saves`, действие `backup` → `root/saves-backup.sh` собирает `tar.gz` из `saves/` и `states/`, держит `KEEP` архивов, пишет статус.
- Найдено тестами и исправлено в `modd`:
  - парсер `module.toml` был нечувствителен к секциям: `id` из `[[start.tiles]]`/`[[pages]]` перетирал id модуля (модуль назывался `main`) → разбор теперь учитывает секции (`[run]`, `[limits]`, остальное — метаданные UI);
  - `entry = "main.sh"` не запускался, т.к. `sh -c main.sh` ищет файл в `PATH`, а не в каталоге модуля → непутевой entry теперь превращается в `./entry`;
  - модули по умолчанию были `enabled = 0` (манифест без ключа молча выключал модуль) → по умолчанию `enabled = 1`.
- Тест проверяет: прямой NDJSON-протокол обоих модулей (`initialize` → `ready`, `action.invoke` → `ok`, набор `ui.update`-целей `tile:*`/`row:*`), работу root-хелперов с подставным `sysfs`/каталогами сейвов, ротацию архивов (`KEEP=2` оставляет 2), и handshake через сам `modd` по UNIX-сокету.
## 2026-11-18 · P3/P7 (образ карты и прошивальщик)

- `board/r36s-v20/layout.json` — пять разделов GPT: BOOT 256 MiB FAT32, SYS_A/SYS_B по 700 MiB squashfs (zstd), DATA 1536 MiB ext4, ROMS — остаток в exFAT; выравнивание 1 MiB. Почему GPT: в MBR только 4 первичных раздела, extended-цепочка на этом классе устройств не нужна.
- `tools/mkimage.py` — детерминированная сборка образа: GUID разделов выводятся из `deepos:<image>:<part>` (одинаковые входы → побайтово одинаковый файл), ФС создаются штатными инструментами (`mkfs.vfat` + `mcopy`, `mksquashfs -comp zstd`, `mkfs.ext4 -d`, `mkfs.exfat`), каждый раздел собирается во временном файле нужного размера и копируется на своё смещение; образ не может «переполнить» раздел — сборка падает с понятной ошибкой.
- `tools/dpflash.py` — запись образа на карту или в файл: `--dry-run`, `--expect-sha256`, `--no-defer-table`. **Таблица пишется последней**: пока первые 34 сектора нулевые, Windows не монтирует разделы, иначе запись падает с `win32=5` (ERROR_ACCESS_DENIED на `\\.\PhysicalDriveN`) — ровно та грабля, что была при прошивке Arch-R. Потоковая запись чанками 4 MiB, без загрузки образа в память.
- `tests/image_test.py` — собирает реальный образ 128 MiB (та же разметка, маленькие размеры) и проверяет: заголовок GPT, 5 разделов и их порядок/выравнивание, метку и сигнатуру FAT32, магию squashfs `hsqs` в обоих слотах, магию ext4 `0xEF53`, сигнатуру exFAT; затем прошивает образ в файл и сверяет sha256 (побайтово), проверяет `--dry-run` (ничего не пишет), отказ при несовпадении sha и при слишком маленькой цели.
- Makefile/CI: `make image-test`, `make image` (полный образ в `build/`), новые шаги в CI; `.gitignore` дополнен `build/`.
## 2026-11-18 · P0/P1 (плата: DTS, конфиги ядра и BusyBox, extlinux, сборка rootfs)

- `board/r36s-v20/dts/rk3326-r36s-v20.dts` — девайсный DTS под нашу плату. Значения взяты из стокового `rf3536k3ka.dtb` (dtc -I dtb -O dts): панель `sitronix,st7703` 640×480, пиксельклок 30 МГц, porch 150/50/150 и 20/6/12, reset `GPIO3_B7` active-low, динамик `gpio3 pin 7`, `hp-det gpio2 pin 3`, батарея 3500 мА·ч, OPP 408/816/1008/1416 МГц. Вендорный драйвер `play_joystick` заменён на mainline-биндинги: `gpio-keys` (16 кнопок) + `adc-joystick` (4 оси стиков) + `adc-keys` (качелька громкости).
- `board/r36s-v20/linux.config` — фрагмент конфигурации ядра: squashfs(zstd), overlayfs, zram/zswap, PSI+memcg, DRM Rockchip + ST7703 + Panfrost + PWM backlight, gpio-keys/keyboard-adc/joystick-adc/saradc, rk817 (MFD/regulator/charger/battery/codec) + simple-audio-card, cpufreq-dt/devfreq, MMC_DW, ext4/vfat/exfat, dwc2 gadget (ACM/NCM/RNDIS/FFS), UART 8250_dw. Модули отключены, лишнее (Wi-Fi/BT/DEBUG_INFO/FB) выключено.
- `board/r36s-v20/busybox.config` — init+ash+mdev, mount/switch_root, tar/gzip, grep/sed/awk/find/xargs, ip/udhcpc, poweroff/reboot, dmesg/ps/free — ровно то, что нужно init и модулям.
- `board/r36s-v20/boot/extlinux/extlinux.conf` — `LABEL DEEPoS`, `LINUX /KERNEL`, `FDT /dtbs/rk3326-r36s-v20.dtb`, root=LABEL=DEEPOS_A (squashfs, ro), `zswap.enabled=1 psi=1`, консоль `ttyS2,1500000n8`.
- `tools/build-rootfs.py` — упаковка staging-дерева в squashfs (`-comp zstd -b 262144`), проверка `--check` (sbin/init, bin/busybox, все три бинаря приложений), `--list`. Метка squashfs не ставится (в squashfs её нет) — метка раздела задаётся в GPT через `layout.json`.
- `tests/board_test.py` (306 мс) — препроцессинг DTS, компиляция dtc, проверка ключевых биндингов (панель, GPIO-кнопки, стики, PMIC, гейдж, звук, 3500 мА·ч, reset GPIO3_B7), конфликтов в фрагменте ядра и его «бloat-списка», апплетов BusyBox, строк extlinux и работоспособности сборщика rootfs (включая отказ на неполном дереве). Настоящая сборка DTB идёт в дереве ядра — тест использует стаб `tests/fixtures/dts/rk3326.dtsi`.
- Makefile/CI: цель `make board-test`, шестой набор в `docker-test`, шаг «Test board layer» в CI; `.gitignore` дополнен `.tmp/`.
- Ограничение MVP: у платы нет линии card-detect, поэтому `broken-cd` (карта опрашивается); вендорные `adc-keys`-таблицы для стиков заменены mainline `adc-joystick` (ось Y не инвертируется в DTS — инверсия в лаунчере/эмуляторе).