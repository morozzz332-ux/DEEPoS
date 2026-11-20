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
## 2026-11-18 · P6/P7 (BOOT-дерево и A/B-переключение слотов)

- `tools/mkboot.py` — собирает содержимое FAT32-раздела BOOT: `KERNEL` (arm64 Image), `dtbs/rk3326-r36s-v20.dtb`, `extlinux/extlinux.conf` (проверяет `LABEL DEEPoS` / `LINUX /KERNEL` / `FDT /dtbs/...`), опционально `logo.bmp` и `MANIFEST.json` с sha256 и размерами всех файлов. Меньше 1 МиБ ядром не считается — ранняя ошибка вместо «тихого» кирпича.
- `tools/update.py` — состояние A/B на разделе DATA (`boot.json`): `slot`, `attempts`, `rollback`, `generation`. Три попытки загрузки — четвёртая переключает слот и поднимает `rollback`; `good` (вызывается, когда лаунчер поднялся) сбрасывает попытки; `switch` двигает слот явно. Запись атомарная (tmp → fsync → rename), битый JSON честно сообщается.
- `tests/boot_test.py` (19 проверок) — раскладка BOOT-дерева и манифест, отказ на маленьком ядре и неправильном extlinux, дефолтный слот A, rollback после трёх неудачных загрузок, сброс через `good`, битое состояние.
- Makefile/CI: `make boot-test`, седьмой набор в `docker-test`, шаг «Test BOOT tree and A/B boot state» в CI.
## 2026-11-18 · P1 (проверка фрагмента ядра на настоящем дереве 6.12.56)

- `tools/kconfig-check.sh` — берёт kernel.org `linux-6.12.56.tar.xz` (кэш в `build/cache`, ~148 МБ, в git не попадает), распаковывает в `/tmp/kbuild`, применяет `make ARCH=arm64 defconfig` + `scripts/kconfig/merge_config.sh .config board/r36s-v20/linux.config` + `olddefconfig` и сверяет результат: каждый `=y` из фрагмента обязан выжить, неизвестные ядру символы печатаются отдельно.
- Первый прогон нашёл 7 мёртвых символов: `ARCH_ROCKCHIP_DT` (нет такого), `ARM_CPU_SUSPEND` (только arm32), `BATTERY_RK817` (в 6.12 гейдж живёт в `CHARGER_RK817`), `MFD_RK808` (правильно `MFD_RK8XX` + `MFD_RK8XX_I2C`), `SND_SOC_ROCKCHIP_RT5651` (нет), `DEBUG_INFO`/`KALLSYMS_ALL` (зависят от `DEBUG_KERNEL`). Фрагмент исправлен.
- Итог после правок: **113 символов, 113 satisfied, 0 неизвестных**. Это уже не «по памяти», а проверка на реальном Kconfig: драйверы панели, PMIC/зарядки/гейджа, кодека, стиков, zram/zswap, squashfs, dwc2 не отвалятся молча из-за переименований.
- Стоимость: один прогон ~3–6 минут (распаковка + kconfig), работает офлайн после первого скачивания.

## 2026-11-18 · P0 (ядро и загрузчик: реальная сборка)

- Добавлен отдельный образ сборки `tools/cross/Dockerfile` (`ubuntu:24.04` + `gcc-aarch64-linux-gnu`,
  `dtc`, `mtools`, `squashfs-tools`, `e2fsprogs`, `exfatprogs`) — `deepos-cross:local`.
- `tools/build-kernel.sh`: скачивает `linux-6.12.56.tar.xz` в `build/cache` (в git не попадает),
  конфигурирует через `defconfig` + `merge_config.sh board/r36s-v20/linux.config` + `olddefconfig`,
  собирает `Image`, компилирует дизайн-плату через `cpp` + `dtc` против **настоящего** дерева
  исходников ядра (а не против стабов из `tests/fixtures/dts`), пишет `build/kernel/BUILD.txt`.
- `tools/mkimage.py`: поддержка загрузчика — `--loader DIR`, `LOADER_OFFSETS`
  (`idbloader.img` → 32 KiB, `u-boot.itb` → 8 MiB), отказ при пустом каталоге.
  Тест в `tests/image_test.py` подтверждает смещения и что загрузчик не портит GPT.
- Разведка: в mainline U-Boot v2025.10 **нет rk3326** (`configs/`, `arch/arm/dts`, `board/rockchip`
  содержат только rk3308/rk3328/…), поэтому загрузчик для этой платы собирается из вендорского
  форка `rockchip-linux/u-boot` (`evb-rk3326_defconfig`, BL31 из `rkbin`).

## 2026-11-18 · P2/P3 (rootfs: busybox, userland, squashfs)

- `tools/build-userland.sh` — кросс-сборка `launcher`, `modd`, `saved` под
  `aarch64-linux-gnu` со статической линковкой (в образе нет glibc помимо busybox).
  Флаги: `-D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L`, `-U_FORTIFY_SOURCE`
  (Ubuntu-заголовки включают fortify и валят сборку на `-Wformat-truncation`).
- `tools/gen-busybox-config.sh` — пересборка `board/r36s-v20/busybox.config` из
  `defconfig` плюс нужные апплеты (mdev, ash, mount, ip, udhcpc, tar). `CONFIG_TC`
  отключён: busybox 1.36.1 не собирается против заголовков 6.x (`struct tc_cbq_wrropt`).
- `tools/build-rootfs.sh` — busybox (static) → `/bin/busybox` с апплетами, наши
  бинарники в `/usr/bin`, overlay (`/etc/os-release`, `inittab`, `init.d/rcS`,
  `fstab`), модули в `/usr/share/deepos/modules`, упаковка в `build/rootfs.squashfs`.
- Артефакт: `build/rootfs.squashfs` 1 867 776 B, 439 записей; `/sbin/init` →
  busybox, `/usr/bin/{launcher,modd,saved}` присутствуют.
- Уроки: `python`-скрипты на Windows пишут CRLF — shell-скрипты портились
  (`set: Illegal option -`), поэтому все `tools/*.sh` пишутся с `newline='\n'`;
  правки C-файлов через PowerShell-`.Replace` с `\n` внутри одинарных кавычек
  дают литеральные ``\n`` в коде — надёжнее править Python-скриптом.

## 2026-11-18 · P0/P2/P3 (ядро 6.12.56, rootfs, образ карты)

- Ядро: mainline 6.12.56, фрагмент `board/r36s-v20/linux.config` (113/113 символов
  выживают `merge_config`), кросс-сборка `aarch64-linux-gnu-` в `deepos-cross:local`.
  Итог: `build/kernel/Image` 74 490 368 B, DTB 46 564 B (собран из реальных
  `rk3326.dtsi`/`px30.dtsi`), sha256 конфига `06daed84…`.
- DTS пришлось выправить под реальные биндинги: `dt-bindings/input/linux-event-codes.h`,
  `&display_subsystem`/`&vopb_out` в `rk3326.dtsi`, метки `&u2phy`/`&u2phy_otg`.
- Rootfs: static busybox 1.36.1 (lean: без cron/syslog/tc) + наши бинарники
  (launcher 598 216 B, modd 597 960 B, saved 663 480 B, static aarch64) +
  overlay (`inittab`, `rcS`, `os-release`) + модули → `build/rootfs.squashfs`
  1 867 776 B (439 записей).
- Образ: `build/deepos-r36s-v20.img` 4 296 015 872 B, sha256 `19130fdb…`,
  GPT 5 разделов (BOOT 256 MiB / DEEPOS_A 700 / DEEPOS_B 700 / DATA 1.5 GiB /
  ROMS ~904 MiB), `mdir` видит KERNEL 74 490 368 B, `dtbs/`, `extlinux/`, `logo.bmp`.
- Открытый блокер: загрузчик. В mainline U-Boot нет RK3326 (только rk3308/rk3328),
  нужен вендорский `rockchip-linux/u-boot` (ветка `next-dev`, `evb-rk3326_defconfig`)
  + BL31 из `rkbin`; `tools/build-uboot.sh` написан, запущен в контейнере, результат
  в `build/uboot.log`. Без `idbloader.img`/`u-boot.itb` образ не стартует на железе.

## 2026-11-18 · P0 загрузчик: вендорский U-Boot собран

- `tools/build-uboot.sh` доведён до рабочего состояния: `rockchip-linux/u-boot`
  (next-dev, `rk3326_defconfig`) + BL31 `rkbin/bin/rk33/rk3326_bl31_v1.37.elf`.
- Три ключевых момента: (1) сборка без `ARCH=arm` (иначе SPL не появляется),
  (2) `KCFLAGS="-Wno-error"` — вендорское дерево не совместимо с новым GCC
  (`common/edid.c`), (3) `make_fit_atf.py` требует ELF-файл BL31 и пакет
  `python3-pyelftools` в кросс-образе; idbloader собирается из `tpl/` + `spl/`
  через `mkimage -T rksd` (как в Arch-R).
- Итог: `idbloader.img` 113 194 B (sha256 `da92d9bb…`), `u-boot.itb` 1 304 064 B
  (sha256 `60bbe765…`), `build/uboot/BUILD.txt` с рефами и хешами.
- Раскладка образа исправлена: `BOOT` теперь начинается с 16 MiB
  (`"start_mib": 16`), чтобы не накрывать загрузчик (32 KiB / 8 MiB);
  `mkimage.py` понимает `start_mib`; первый раздел больше не перетирает boot chain.
- Полный образ с загрузчиком: `build/deepos-r36s-v20.img` 4 311 744 512 B,
  sha256 `cabbf277…`; проверено: `RK33` по 32 KiB, FIT по 8 MiB (FDT 2617 B +
  1.3 MB данных), FAT32 `BOOT` по 16 MiB, `EFI PART` по LBA1.

## 2026-11-18 · P6/P7 (updatr: A/B на устройстве без Python)

- Новый `apps/updatr/src/updatr.c` — C-двойник `tools/update.py`: `status`,
  `decide`, `begin`, `good`, `switch A|B` и `install --slot A|B --file IMG --dev TARGET`.
  Состояние `boot.json` пишется атомарно (tmp → fsync → rename → fsync dir), битый
  JSON не ломает запуск (значения падают в дефолт), коды возврата: 2 i/o, 3 аргументы,
  4 цель меньше образа.
- `tools/build-userland.sh` собирает `updatr` статически вместе с остальными;
  rootfs-overlay `rcS` теперь делает `updatr begin` при старте и `updatr good`
  через 20 с работы userspace (в образе нет init-системы/вотчдога).
- `tests/updatr_test.py` — 21 проверка: дефолт слота A, три попытки держат слот,
  четвёртая переключает и ставит `rollback`, `good` и `switch`, отказ на плохой слот,
  установка образа в файл-заглушку, отказ на маленькую цель, терпимость к битому state.
- Проводка: `make updatr`, `make updatr-test`, `docker-test` гоняет 8 наборов,
  `board_test` требует `apps/updatr/updatr` в staging.
- Итог: rootfs 2 097 152 B (с `updatr`), образ пересобран, все 8 наборов зелёные.

## 2026-11-18 · P4 (ввод и навигация лаунчера)

- `apps/launcher/src/dp_input.{h,c}`: evdev-бэкенд без `<linux/input.h>` (в musl-образе
  нет kernel headers, поэтому константы ABI объявлены локально), перебор
  `/dev/input/event0..31`, `EVIOCGNAME`, предпочтение устройствам с `r36s`/`deepos`/
  `gamepad`/`gpio-keys` в имени; маппинг `BTN_SOUTH→A`, `BTN_EAST→B`, `BTN_NORTH→X`,
  `BTN_WEST→Y`, `BTN_TL/TR→L1/R1`, `KEY_UP/DOWN/LEFT/RIGHT`, `KEY_ENTER→A`,
  `KEY_ESC→B`, `KEY_SELECT`, `KEY_START`.
- Навигация в `main.c`: 6 вкладок (continue, games, settings, modules, files, info),
  игры двухуровневые (список систем → список игр), `B` возвращает на уровень выше,
  `LEFT/RIGHT` листают вкладки с заворачиванием, `UP/DOWN` двигают курсор с упором
  в границы, `quit` завершает цикл.
- CLI для host-тестов: `--keys "RIGHT,DOWN,A"` (синтетические нажатия) и
  `--print-state` (`screen=<id> level=<n> sel=<n> system=<n>`); без `--keys` и без
  `--out` лаунчер открывает evdev и работает интерактивно.
- `tests/input_test.py` — 17 проверок: дефолтное состояние, курсор и его границы,
  переключение вкладок в обе стороны с заворачиванием, вход в систему/игры и возврат,
  размер списка игр, отказ на неизвестную клавишу (`rc=2`), `quit`, а также кадр,
  отрисованный после синтетических нажатий.
- Сборка: в `apps/launcher/Makefile` добавлен `-D_GNU_SOURCE` (иначе `strcasecmp`/
  `strcasestr` скрыты при `-std=c11 -Werror`), запрос `EVIOCGNAME` приводится к `int`.
- `make input-test`, `docker-test` и `tests/run-all.sh` теперь гоняют 9 наборов.

## 2026-11-18 · P4b/P4 (лаунчер ↔ modd: живой список модулей)

- `apps/launcher/src/dp_modc.{h,c}`: синхронный клиент modd по AF_UNIX —
  `dp_modc_call(sock, method, params, out, n)` шлёт одну NDJSON-строку
  `{"id":1,"method":…,"params":…}`, читает ответ построчно, достаёт `result`;
  `dp_modc_status(sock, m)` разбирает `{"modules":[{"id":…,"state":…}]}` в
  `m->mods[] / m->nmods` (до `DP_MAX_MODULES = 8`).
- Экран «МОДУЛИ» больше не статичен: при живом `modd` рисуется реальный список,
  подпись = `id`, вторая строка — русская расшифровка состояния (`ready` →
  «включён · отвечает на запросы», `stopped` → «остановлен · запустится при
  действии», `disabled` → «отключён · три падения за 10 минут»), тумблер включён
  только для `ready`; шапка показывает `modd · N модулей · M активных`. Без сокета
  остаётся демо-набор (чтобы golden-кадры не зависели от окружения).
- CLI: `--modules-socket PATH` (по умолчанию `/run/modd.sock`) и `--print-modules`
  (`<id>\t<state>` построчно) — удобно и для тестов, и для отладки на устройстве.
- `tests/launcher_mod_test.py`: поднимает настоящий `modd` на временном сокете с
  фикстурами `thermal/hang/crash`, проверяет получение списка и состояний, рендер
  экрана «МОДУЛИ» из живых данных и мягкий фолбэк при отсутствии сокета (6 проверок).
- `tests/ci/render-modules.sh` — демо-рендер экрана с живым modd (использован для
  `build/modules-live.png`); `make launcher-mod-test`, `tests/run-all.sh` — 10 наборов.

## 2026-11-18 · P4 (вывод на экран: fbdev / RGB565)

- `apps/launcher/src/dp_display.{h,c}`: вывод кадра без libdrm/EGL/композитора —
  `open(/dev/fb0)` + `FBIOGET_VSCREENINFO/FSCREENINFO` (структуры ABI объявлены
  локально, как и для evdev) + `mmap`; блит поддерживает 16 bpp RGB565 (основной
  путь через DRM fbdev emulation), 24 и 32 bpp; `dp_display_present()` копирует
  canvas построчно с учётом `line_length`.
- Для host-тестов тот же код умеет писать в обычный файл: если ioctl-запросы не
  отвечают, а путь не является устройством, берётся 640×480×16, файл
  `ftruncate`-ится до нужного размера и `mmap`-ится — блит получается
  побайтово сравнимым с PPM-рендером.
- `main.c`: `--fb PATH` (по умолчанию `/dev/fb0`); при интерактивной работе кадр
  перерисовывается и выводится после каждого нажатия; если дисплей открыть нельзя,
  лаунчер не падает: при явном `--fb` возвращает код 1 с «no display», без него
  просто работает как раньше.
- Ядро: в `board/r36s-v20/linux.config` включён `CONFIG_DRM_FBDEV_EMULATION=y`
  (символ `..._32BPP_ONLY` в 6.12 отсутствует — убран); `tools/kconfig-check.sh`
  подтвердил 114/115 символов на настоящем дереве.
- `tests/display_test.py` — 8 проверок: полный кадр 640×480×2 для трёх экранов,
  побайтовое совпадение с PPM→RGB565, кадр после `--keys`, отказ при недоступном
  фреймбуфере.

## 2026-11-18 · P4b (лаунчер вызывает действия модулей)

- `dp_modc_action(sock, module_id, action)` — вызов `action.invoke` через `modd`
  (`params {"module":…,"action":…}`), успех = `"ok":true` в `result`.
- CLI: `--module-action ID:ACTION` (`launcher --module-action thermal:eco`).
  Неверный формат → код 2 и подсказка, отказ модуля/таймаут → код 1.
- Сквозной тест: `launcher_mod_test.py` поднимает `modd` с фикстурами, дергает
  `thermal:eco` и проверяет строку в `$MODD_MODULE_DATA/actions.log`, затем
  `thermal` без действия → код 2. Всего 8 проверок в наборе.

### Пересборка артефактов после fbdev

- Ядро: `build/kernel/Image` 74 490 368 B, `kernel.config` sha256
  `06daed84e9b8889bc564872ec26b0e64b1b15ce3841124309fb387366ea22d3a` — sha256 не
  изменился, потому что `CONFIG_DRM_FBDEV_EMULATION=y` и так включён
  (`DRM_ROCKCHIP` его выбирает); строка во фрагменте оставлена явно, чтобы
  зависимость не потерялась при смене defconfig.
- Userland: launcher/modd/saved/updatr статически (aarch64), rootfs
  `build/rootfs.squashfs` 2 101 248 B, внутри `usr/bin/{launcher,modd,saved,updatr}`.
- BOOT-дерево пересобрано (`MANIFEST.json` с sha256 каждого файла), образ:
  `build/deepos-r36s-v20.img` 4 311 744 512 B,
  sha256 `e9a1d0100c16ec0a1f602e0ce3b94c553c5594bce6914318d9f7e38a3b44f6ab`.

- Golden-хэши обновлены осознанно: экран «МОДУЛИ» теперь рисует шапку
  «modd не запущен · демо-данные» при отсутствии сокета, а экран игр подсвечивает
  строку по текущему `sel`; поведение зафиксировано в `tests/golden/hashes.json`.

## 2026-11-18 · P4/P7 (запуск игры: hook модулей и команда эмулятора)

- `apps/modd` получил метод `launch.before`: широковещательный опрос модулей
  (`params = {"system","rom"}`), агрегирование ответов `{"decision":"allow|deny"}`;
  модуль, который не отвечает или падает, пропускается — модули совещательные и
  не должны блокировать запуск, если их нет. Фикстура `tests/fixtures/modd/hook`
  отвечает `allow`, но `deny` на ROM с `blocked` в имени.
- Лаунчер: `dp_modc_launch()` (клиент), `--run-game SYSTEM:ROM`, `--emulators PATH`
  (по умолчанию `/data/emulators.toml`). Порядок: hook → поиск команды по системе →
  подстановка `%ROM%` в полный путь `<roms>/<system>/<name>` → `sh -c` → ожидание.
  Коды: 0 — игра завершилась успешно, 1 — эмулятор упал, 2 — плохой аргумент,
  4 — запрещено модулем (печатает `blocked<TAB>system<TAB>rom`), 5 — нет команды.
- Парсер `emulators.toml` терпим к кавычкам и пробелам вокруг `=`; строки с `#`
  и без `=` пропускаются.
- `board/r36s-v20/data/emulators.toml` — образец из 7 систем (retroarch + пути
  к ядрам); `make image`/`image-full` копируют его в `build/data` перед сборкой.
- Тесты: `tests/launch_test.py` (12 проверок: успешный запуск и argv заглушки,
  неизвестная система, кривой аргумент, падение эмулятора, allow/deny через
  настоящий `modd`) и расширенный `tests/modd_test.py` (проверки `launch.before`).
- Итог: 12 наборов зелёные; образ пересобран с новым лаунчером и командой запуска,
  `build/deepos-r36s-v20.img` sha256 `7b403aa9e80c0fc71e5df8c8232aa8a518a343fd1c421dc05b3063e1adfe0a6c`,
  размер 4 311 744 512 B; idbloader/u-boot.itb на местах (сверены побайтово).

## 2026-11-18 · P4 (слот сейва в команде запуска, проверки DATA)

- Лаунчер: `--save-slot N` и тег `%SLOT%` в `emulators.toml` (0, если игра
  запускается из библиотеки). Вывод успешного запуска теперь содержит слот:
  `launch<TAB>system<TAB>rom<TAB>slot=N<TAB>exit_code`.
- Тесты образов/платы усилены там, где раньше была только «сигнатура ФС»:
  `tests/image_test.py` монтирует DATA через `debugfs` и читает реальный файл
  (проверяет, что данные из `build/data` действительно попали в раздел — именно
  так в образ попадает `emulators.toml`); `tests/board_test.py` проверяет, что
  `board/r36s-v20/data/emulators.toml` существует, содержит >=3 маппинга и все
  строки используют `%ROM%`.
- `Makefile`: host-сборка лаунчера теперь всегда начинается с `clean` — иначе
  после кросс-сборки в `src/*.o` оставались aarch64-объекты и ld падал
  `file in wrong format` (грабли повторялись дважды).

## 2026-11-18 · P4 (запуск игры со строки «Продолжить»)

- Экран «Продолжить» теперь запускает игру: A на записи → `modd` hook `launch.before` →
  эмулятор из `/data/emulators.toml` с подстановкой `%ROM%` и `%SLOT%` (номер слота из
  записи). Логика запуска вынесена в общую `launch_game()` — её используют и `--run-game`,
  и интерактивный экран, поэтому поведение и коды возврата (0/1/4/5) совпадают.
- `continue.tsv` расширен до 7 колонок: `title, system_display, meta, slot, has_save,
  sys_id, rom`. Старые 5-колоночные строки остаются валидными — они рисуются, но не
  запускаются (нет файла ROM), то есть формат обратно совместим.
- Поймана и исправлена классическая ошибка: `struct dp_nav nav;` объявлялся без
  инициализации, и новые поля (`launch/lsys/lrom/lslot`) содержали мусор — лаунчер
  «запускал» пустую игру (`no emulator for ''`). Теперь `struct dp_nav nav = { 0 };`.
- Тесты: `tests/launch_test.py` получил два кейса на «Продолжить» (запуск с правильным ROM
  и слотом 2; строка без ROM не запускает) — всего 12 наборов зелёные.
- Правило, закреплённое в процессе: патчи-скрипты обязаны проверять якорь (`assert old in s`),
  иначе замена молча не применяется (на этом потеряли полчаса).

## 2026-11-18 · P4 (--selftest и единый прогон тестов)

- `launcher --selftest` печатает окружение в формате `ключ=значение`:
  `version`, `roms=… systems=N games=M`, `data=… continue=N`,
  `emulators=… emulators_present=0|1`, `modd=… modules=N`, `fb=… fb_present=0|1`,
  `input_events=N`, `status=ok`. Это первое, что нужно запускать на новой консоли:
  сразу видно, что не завелось — ROM, `emulators.toml`, `/dev/fb0`, ввод или `modd`.
- `tests/selftest_test.py` проверяет контракт: пустые каталоги не роняют отчёт,
  счётчики считаются, отсутствие сокета `modd` даёт `modules=0`. Ключи с одинаковыми
  именами разведены (`emulators_present` / `fb_present`), иначе парсер тестов склеивал
  `present` из двух строк.
- Найдено в тесте: `--selftest` сначала вернул 0 и пустой вывод — в аргументах не
  передавался сам флаг (тест падал не там, где искали). Отдельный скрипт-проба
  `deepos/.tmp/probe_selftest.py` теперь проверяет такие вызовы до запуска набора.
- CI переписан на один шаг: `tests/run-all.sh` в том же Docker-образе собирает
  четыре приложения и гоняет все наборы; раньше часть шагов запускалась на раннере
  без `mtools`/`dtc` и не могла пройти.
- Тестовых наборов стало 13; образ пересобран с `--selftest`.

## 2026-11-18 · P4 (список «Продолжить» обновляется после игры)

- Лаунчер после успешного запуска (код 0) переписывает строку этой игры в
  `/data/continue.tsv`: строка встаёт первой, получает фактический слот, `has_save=1`
  и мету «недавно», старые строки сохраняются (до `DP_MAX_CONTINUE` = 12).
  Раньше список был статичным файлом, и «Продолжить» не отражал реальные сессии.
- Запись атомарная: `continue.tsv.tmp` → `fflush`+`fsync` → `rename` → `fsync(dir)`;
  при сбое питания остаётся либо старый файл, либо новый, но не полузапись.
- Дубликаты не появляются: существующая строка с тем же `sys_id`+`rom` вырезается и
  заменяется новой (проверено тестом на два последовательных запуска с разными слотами).
- `tests/launch_test.py`: два новых кейса — запись строки после `--run-game` (7 колонок,
  слот, `has_save`, сохранение прежних записей, отсутствие `.tmp`) и повторный запуск
  без дублей с обновлением слота.
- Образ пересобран: `build/deepos-r36s-v20.img` sha256 `3701b7211369ad273220662282c82ca7a43049ab217f9a4b654e2663e557f93f`.

## 2026-11-18 · P6/P7 (A/B учитывается при загрузке, extlinux ведёт слот)

- `board/r36s-v20/rootfs-overlay/etc/init.d/rcS`: BOOT-раздел (`mmcblk1p1`) монтируется в
  `/flash`; блок A/B-учёта перенесён **выше** `exit 0` (раньше он был мёртвым кодом) и теперь
  вызывает `/usr/bin/updatr --state /data --boot /flash begin`, а через 20 с — `good`.
- `apps/updatr/src/updatr.c`: `sync_boot()` подключён к ветвям `begin` и `switch` — при смене
  слота (в том числе при откате после четвёртой неудачи) переписывается
  `root=LABEL=DEEPOS_A|B` в `<boot>/extlinux/extlinux.conf` (tmp → fsync → rename).
  Загрузчик не читает JSON, поэтому выбор слота обязан жить в его конфиге.
- `tests/updatr_test.py`: 9 новых проверок (extlinux указывает на B, прочие строки целы,
  `.tmp` не остался, обратный `switch A`, откат после 4-го `begin` переписывает конфиг,
  отсутствующий каталог загрузчика → rc 2).
- `tests/board_test.py`: `test_rcs_order()` — `/flash` монтируется, `--boot /flash` передан,
  `begin`/`good` идут до `exit 0` (защита от возврата мёртвого кода).
- 13 наборов тестов зелёные; rootfs 2 109 440 B, BOOT-дерево `0.5-dev`, образ
  `build/deepos-r36s-v20.img` 4 311 744 512 B sha256 `4f921aa551cc1020d9ffc9e5e4625bb81c2f97d1f4c78a0878db8bc4e2e14dc7`.
- Урок: вставка блока в Python-тест после `if failures:` даёт `IndentationError`; блок надо
  класть в тело `try` перед `finally`, а переменные в тесте называются `state`/`tmp`
  (не `state_dir`). Скрипты-патчи обязаны проверять якорь (`assert old in s`), иначе молча
  ничего не меняют.
- Следующий шаг: этап 2 — запись образа на карту и первый буст на устройстве.

## 2026-11-18 · P7 (проверка образа до записи: две критичные ошибки)

- Написан `tools/verify-image.py` — офлайн-проверка готового образа перед записью на карту:
  protective MBR, первичный и резервный GPT (CRC заголовка и массива записей), имена и
  выравнивание разделов, отсутствие перекрытий, сигнатуры FAT32/squashfs/ext4/exFAT,
  побайтовая сверка idbloader (32 KiB) и u-boot.itb (8 MiB), содержимое BOOT (`mdir -/`,
  разрешение длинных имён VFAT), `MANIFEST.json` и sha256 `KERNEL` (через `mcopy`),
  наличие обязательных файлов в squashfs (`unsquashfs -o`).
- Проверка сразу нашла **две ошибки, из-за которых образ не загрузился бы**:
  1. `mkimage` вызывал `mksquashfs <файл build/rootfs.squashfs>` — в раздел `DEEPOS_A`
     попадал squashfs, содержащий **один файл** `rootfs.squashfs`, а не корень системы.
     Теперь готовый squashfs копируется как есть (`make_squashfs` различает файл и каталог).
  2. GPT писался с `entries_crc` от одного набора записей, а на диск попадал другой;
     плюс `fill`-раздел не вычитал 16 MiB, зарезервированные под boot chain (образ вырастал
     на 16 MiB, резервный GPT оказывался внутри ROMS). `write_gpt` переписан по спецификации
     (зануление 34 секторов в начале и конце, записи в LBA2 и LBA-33, `first/last usable`),
     добавлена самопроверка CRC и наличия резервного заголовка сразу после записи.
- Загрузчик в образе проверяется побайтово: `idbloader.img` (113 194 B) на 32 KiB,
  `u-boot.itb` (1 304 064 B) на 8 MiB.
- Тесты: в `tests/image_test.py` добавлены `verify_checks()` — «хороший образ принимается»
  и «испорченный байт в массиве GPT ловится по CRC записей»; цель `make verify-image`.
- 13 наборов тестов зелёные; образ `build/deepos-r36s-v20.img` **4 294 967 296 B** (ровно
  4096 MiB), sha256 `6cf5a8be2ab34f037763a49a152525662b5974f7355347e61304a4fc9166ecf7`,
  проверка: `PASS verify-image: 39 checks`.
- Следующий шаг: этап 2 — записать образ на карту (`tools/dpflash.py`) и проверить первый
  буст на устройстве.

## 2026-11-18 · P8 (настройки: сохранение и применение без композитора)

- Новый модуль `apps/launcher/src/dp_config.{h,c}`: настройки в
  `/data/config/settings.toml` (`brightness`, `volume`, `profile`), разбор `key = value`
  с комментариями `#`, запись атомарная (`tmp` -> `fsync` -> `rename`), кривые значения
  отвергаются, битая строка не роняет чтение остальных.
- Применение без композитора: яркость пишется прямо в sysfs backlight
  (`backlight/deepos-bl|backlight|pwm-backlight`), профиль CPU — в `<data>/cpu-profile`
  (его читает `cpu-profile.sh` на Arch-R; в DEEPoS тему подхватывает будущий
  `thermal`-модуль). Нет sysfs-узла — просто ничего не трогаем.
- CLI лаунчера: `--config`, `--set KEY=VAL`, `--print-config`, `--apply`, `--sysfs PREFIX`.
  По умолчанию настроек нет и устройство не трогается (`brightness=0`, `volume=0`).
- `tests/config_test.py` — 18 проверок: дефолты без файла, сохранение и загрузка трёх
  ключей, отказ на `brightness=150`/`profile=turbo`/неизвестный ключ (rc 2, файл не
  меняется), `--apply` пишет backlight (40 % -> 18 из 45) и профиль, битый файл
  терпится (`brightness = abc` отбрасывается, остальные ключи живы).
- `tests/run-all.sh` — 14 наборов; `make config-test`. Все наборы PASS.
- Образ пересобран: rootfs 2 113 536 B, BOOT-дерево `0.6-dev`, образ
  `build/deepos-r36s-v20.img` 4 294 967 296 B,
  sha256 `505f1c6b9a620542e72e173a9528fcae4988deeeb4dd43bed960af7b67eda518`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P0/P4 (исправлена привязка разделов к точкам монтирования)

- Найдено расхождение между `board/r36s-v20/layout.json` и `rcS`: старый `rcS` монтировал
  **p4 (DATA, ext4) в `/storage`**, а **p3 (SYS_B, squashfs, read-only) в `/data`** — то есть
  настройки и A/B-состояние писались бы в системный слот, а ROM-библиотека указывала на пустой
  раздел. Теперь раскладка ровно как в GPT:
  `p1 BOOT -> /flash`, `p4 DATA -> /data`, `p5 ROMS -> /storage`; системные слоты p2/p3 в
  рантайме не монтируются (p3 теперь вообще не трогается).
- Лаунчер по умолчанию читает библиотеку из корня ROMS-раздела (`/storage`), а не из
  `/storage/roms` — на exFAT-корне лежат папки систем (`md/`, `snes/`, …), как их видит ПК.
- Модули переехали с ROM-раздела на DATA: `/data/modules` и `/data/module-data` (ROM-раздел
  общий с ПК, писать туда служебное нельзя).
- `tests/board_test.py`: новая группа `test_partition_mounts()` (7 проверок) — p1→/flash,
  p4→/data, p5→/storage, отсутствие старых привязок, пути модулей на DATA.
- `tests/run-all.sh` чистит host-объекты перед прогоном: после кросс-сборки в `src/*.o`
  остаются aarch64-объекты и линковка падала `file in wrong format`.
- Все 14 наборов PASS. Образ пересобран: rootfs 2 113 536 B, BOOT `0.7-dev`,
  `build/deepos-r36s-v20.img` 4 294 967 296 B,
  sha256 `2569c4b70f510d562d31198d272ae321a6e81a3ad65cf7aa1f50cead38916fd7`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P0 (rcS перестал быть хрупким)

- `rcS` больше не может сорвать загрузку: убран `errexit`, все `mount` стали
  best-effort (`2>/dev/null || true`), добавлен помощник `mount_part`, который пропускает
  уже смонтированные точки (`/proc/mounts`) и отсутствующие устройства. До этого один
  неудачный mount (повторный запуск init, отсутствующая карта, уже смонтированный
  devtmpfs) обрывал скрипт до монтирования DATA/ROMS и до A/B-учёта.
- Создаются каталоги, которые ждёт лаунчер: `/data/config` и `/data/saves`.
- A/B-учёт теперь выполняется только при **реально смонтированном** `/data`
  (`is_mounted /data`): иначе счётчик попыток терялся бы на каждом бусте, а при отсутствии
  карты — мог бы переключить слот на пустом разделе.
- Модули стартуют только если `/data/modules` существует; ROM-раздел (`/storage`) остаётся
  чистым — на нём живёт библиотека, общая с ПК.
- `tests/board_test.py`: новая группа `test_rcs_robustness()` — 13 проверок: отсутствие
  `set -e`, наличие `/data/config` и `/data/saves`, guard `is_mounted /data`, помощник
  `mount_part`, «best-effort» на каждой строке `mount`, плюс `sh -n` (POSIX-синтаксис).
- Все 14 наборов PASS. Образ пересобран: rootfs 2 121 728 B, BOOT `0.8-dev`,
  `build/deepos-r36s-v20.img` 4 294 967 296 B,
  sha256 `bf04b4dbf32d3d9bcfabaa41ab71f179c0a36916bbb02ddd9af5eedc1f16b6c5`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P0 (передача управления UI и проверка готовности)

- `rcS` теперь в конце печатает готовность окружения для серийной консоли:
  `DEEPoS: storage=ok|missing data=ok|missing` (по факту `/proc/mounts`), после чего `exit 0`.
- UI запускается штатно инициативой из `/etc/inittab` (`::respawn:/usr/bin/launcher`),
  поэтому упавший лаунчер поднимается сам, без init-системы и без сторожевого демона.
- `tests/board_test.py`: новая группа `test_boot_handover()` — 8 проверок: readiness-строка,
  запуск лаунчера из inittab, `::sysinit` для `rcS`, `::shutdown`, наличие overlay-файлов
  (`etc/init.d/rcS`, `etc/inittab`, `etc/os-release`) и бит исполнения на `rcS`.
- Все 14 наборов PASS. Образ пересобран: BOOT `0.9-dev`,
  `build/deepos-r36s-v20.img` 4 294 967 296 B,
  sha256 `95227b2595af00cc7ba07359f8edc360cd3a2c856505f6b743f1a83f85c51429`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P8 (первый буст на пустой карте: подсказка вместо пустого экрана)

- Экраны «ИГРЫ / СИСТЕМЫ» и «ПРОДОЛЖИТЬ» получили пустое состояние: при `nsys == 0`
  по центру рисуется «Библиотека пуста · Скопируйте папки систем на карту · ROM-раздел виден
  с ПК по USB», при `ncont == 0` — «Нет недавних игр · Запущенная игра появится здесь».
  Раньше на свежей карте был просто чёрный экран без объяснений.
- Счётчик в шапке склоняется по-русски: `dp_games_word()` (`1 игра`, `2–4 игры`,
  `0/5–20/11–14 игр`) — раньше всегда было «игры» (`1901 игры`).
- `tests/run.py`: новые проверки пустого состояния — рендер `systems` и `continue` с пустым
  ROM-каталогом, в теле кадра должно быть ≥6 строк «чернил» (подсказка реально нарисована).
  Golden-хэши обновлены осознанно (изменилась шапка систем).
- Все 14 наборов PASS. Образ пересобран: BOOT `0.10-dev`,
  `build/deepos-r36s-v20.img` 4 294 967 296 B,
  sha256 `04e5df4738e8db991dd98aabab8c77d2c716d13036d5c0f845e47e90bb7a83bc`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P8 (экран настроек показывает реальный settings.toml)

- `model_load_config(struct dp_model *, const char *config_path)` в `apps/launcher/src/main.c`:
  грузит `/data/config/settings.toml` (или `--config`) в поля модели `cfg_brightness`,
  `cfg_volume`, `cfg_profile` — теперь значения видны и в рендере, и в `--selftest`
  (строка `config=… brightness=… volume=… profile=…`). Раньше настройки загружались
  только в CLI-ветке `--apply`, а экран оставался статичным.
- Карточки «Дисплей», «Звук», «Питание» собирают подпись из модели: `яркость N%` /
  `не задана`, `динамик · N%` / `не задан`, `eco|balanced|max · CPU` / `авто · CPU`
  (короткие фразы выбраны так, чтобы не вылезать за 200 px карточки).
- `tests/selftest_test.py`: новый кейс с `settings.toml` (`brightness = 40`,
  `volume = 55`, `profile = eco`) — проверяются `config`, `brightness`, `volume`, `profile`.
- Найден и закрыт ловкий NPE в проверке: мой рендер экрана шёл не через `run.py`, а через
  устаревший `tests/out/*.ppm` от `tests/ci/render-all.sh`, поэтому визуальная проверка
  показывала старый текст. Правило: **визуальные кадры обновляет только
  `sh tests/ci/render-all.sh <root> <out>`, а `tests/run.py` рендерит во временный каталог**.
- Все 14 наборов PASS, golden обновлены осознанно (подписи карточек).

## 2026-11-18 · P8 (экран файлов показывает реальное состояние разделов)

- В модели появились `roms_ok` (ставится в `dp_model_scan`, когда каталог ROM открылся)
  и `data_ok` (в `dp_model_load_continue`, `access(data_dir, R_OK | W_OK)`), плюс
  `--selftest` печатает `data_ok=` и `roms_ok=` — на устройстве это первое, что покажет,
  смонтировались ли DATA/ROMS.
- Экран «ФАЙЛЫ И ПЕРЕДАЧА»: новая строка «Разделы» с подписью `data — ok · roms — ok`
  (или «нет») и цветом `DP_COL_ACC`/`DP_COL_WARN`; строка «ROM'ы» теперь считает свободное
  место из `rom_total_mb - rom_used_mb` (`24 ГБ свободно`), а не печатает константу.
- `tests/selftest_test.py`: `data_ok=1 roms_ok=1` для нормального окружения, `0/0` для
  пустого, и отдельный кейс «ROM-раздел отсутствует, но `continue.tsv` на DATA есть» →
  `continue=1`, `roms_ok=0` (история недавних игр не зависит от карты с играми).
- По пути пойман и исправлен собственный баг: скрипт правки записал содержимое `dp_scan.c`
  в `dp_model.h` (заголовок стал включать сам себя: `In file included from src/dp_model.h:1,
  from src/dp_model.h:1, …`); файл восстановлен из git и правки применены заново.
- Все 14 наборов PASS, golden обновлены. Образ `0.12-dev`:
  sha256 `e8e4273a7ba7e3ec269c3b2d3bbaedfdfd19b1acee349bf08bd3db6d5a5ccfd3`,
  `PASS verify-image: 39 checks`.

## 2026-11-18 · P7 (preflight: одна команда GO/NO-GO перед записью карты)

- `tools/preflight.py` — проверяет артефакты так, как их использует загрузка:
  размер `build/kernel/Image` (>= 10 МиБ), наличие `compatible = "deepos,r36s-v20"`
  и строки `sitronix,st7703` в DTB, `LABEL DEEPoS` и `LINUX /KERNEL` в `extlinux.conf`,
  **совпадение имени FDT из extlinux с реальным файлом в `BOOT/dtbs`** (частая опечатка =
  тихий небут), `BOOT/KERNEL` побайтово равен ядру и его sha256 сходится с `MANIFEST.json`,
  в squashfs есть `sbin/init`, `bin/busybox`, `usr/bin/{launcher,modd,saved,updatr}`,
  `etc/init.d/rcS` с битом `x`, `etc/inittab`, `etc/os-release`; наличие обоих загрузчиков;
  в конце — `tools/verify-image.py` (GPT, backup GPT, сигнатуры ФС).
- Вывод: `ok/FAIL` по каждой проверке и итог `PREFLIGHT: GO (32 checks)` или
  `PREFLIGHT: NO-GO (n of m failed)`; код возврата 0/1.
- `tests/preflight_test.py`: синтетическое дерево (11 МиБ «ядро», DTB с нужными строками,
  extlinux, MANIFEST с sha256, squashfs из staging с симлинком `sbin/init`, загрузчики)
  → GO; переименованный DTB в `BOOT/dtbs` → NO-GO с упоминанием `fdt file exists`;
  rootfs без `usr/bin/launcher` → NO-GO.
- На реальной сборке: `PREFLIGHT: GO (32 checks)`.
- Проводка: `make preflight` / `make preflight-test`, `tests/run-all.sh` — 15 наборов,
  CI получил шаг «Preflight self-test», в `docs/DEVICE-TEST-PLAN.md` — §0.4a
  «Проверка готовности» с правилом «NO-GO — карту не писать».

## 2026-11-18 · P8 (метрики рендера, отчёт с устройства, статус прототипа)

- `tests/ci/measure.py` теперь печатает время отрисовки каждого экрана (лучшее из 5 прогонов,
  host): `continue 10.3`, `systems 10.7`, `games 10.2`, `settings 10.0`, `modules 10.2`,
  `files 10.3`, `info 9.4` мс; `launcher_bytes=85 208`, `test_ms=1 179`, `render_ms=2 648`.
  Это верхняя граница «первого кадра» на x86-контейнере; на 4×A35 ожидание — в разы больше,
  но порядок понятен и регрессии будут видны сразу.
- `docs/PROTOTYPE-STATUS.md` переписан под текущее состояние: 15 наборов тестов, строка
  «Готовность» (preflight 32 проверки), «Загрузка системы» (mounts/order/handover/robustness),
  «Настройки» (settings.toml → UI), актуальный sha256 образа `0.12-dev` и честный список
  «не проверено на железе» с указанием, чем проверять.
- `docs/DEVICE-TEST-PLAN.md` §7 «Отчёт с устройства»: готовый набор команд (selftest, mounts,
  free + PSI, температуры, A/B, питание, dmesg по mmc/panel/rk817/gadget) и таблица
  «эталон host → факт на устройстве», чтобы разговор по железу был предметным.

## 2026-11-18 · P0/P9 (отладочный UART: getty на ttyS2)

- `board/r36s-v20/rootfs-overlay/etc/inittab`: добавлена строка
  `ttyS2::respawn:/sbin/getty -L ttyS2 1500000 vt100` — без неё любая ошибка загрузки
  на железе выглядит как «чёрный экран»; с ней на гребёнке UART (3.3V TX/RX/GND) есть
  логин и шелл. BusyBox уже собран с `CONFIG_GETTY=y` и `CONFIG_LOGIN=y`.
- Добавлены `etc/passwd` (`root::0:0:DEEPoS root:/:/bin/sh`) и `etc/group` (`root:x:0:`):
  пароля у root нет намеренно — это физический порт, ограничение описано в
  `docs/DEVICE-TEST-PLAN.md`.
- `tests/board_test.py::test_boot_handover`: +5 проверок (getty на ttyS2 с 1500000,
  запись root в passwd, root в group, `CONFIG_GETTY=y`, `CONFIG_LOGIN=y`).
- Проверка сборки: 15 наборов PASS, `PREFLIGHT: GO (32 checks)`, `verify-image: 39 checks`,
  в squashfs есть `etc/passwd`, `etc/group`, `etc/inittab`.
- Образ `0.13-dev`: 4 294 967 296 B, sha256 `349a900d6b318888851e35a2260893db2b7eadfb4ec99e08b194935e0d4bf2c3`.

## 2026-11-18 · состояние стенда перед этапом 2

- Консоль подключена к ПК по USB-NCM и работает под Arch-R: адаптер `Ethernet 4` (idx 11),
  адреса `<pc-ip>/24` + `<pc-link-local>/16`, открыты `<console-ip>:22` (SSH) и `:8080`
  (веб-панель ArchR), вторая сеть консоли тоже отвечает.
- Внешний диск `X:` («Внешний», NTFS) на месте, свободно 250.5 ГБ (там бэкап `BOOT` и
  `EASYROMS` с прошлой Arch-R-установки).
- **SD-карты в картридере нет** (`Get-Disk` видит только NVMe и внешний HDD) — для записи
  DEEPoS карту нужно вставить в картридер.

## 2026-11-18 · P9 (release-отчёт и безопасный выбор карты)

- `tools/dpflash.py --list`: номер `PhysicalDriveN` больше не угадывается. На Windows
  список берётся из `Get-Disk` (Number / FriendlyName / Size / BusType / PartitionStyle),
  на Linux — из `/sys/block` (пропускает loop/ram/zram, печатает removable и модель).
- `tools/release.py`: пишет `docs/RELEASE.md` — sha256 и размеры образа, ядра, DTB,
  rootfs, загрузчиков, версию BOOT из `build/boot/MANIFEST.json` и git-ветку/коммит,
  плюс блок команд, которые надо выполнить перед записью на карту.
- `tests/release_test.py`: синтетическое дерево → sha256/размер/версия в отчёте,
  отсутствие байтов артефактов, guard `exit 2` при пропавшем образе и `--allow-missing`.
- В `tests/ci/Dockerfile` добавлен `git` (без него в отчёте было `git: ?`).
- Проверка: 16 наборов PASS, отчёт `docs/RELEASE.md` соответствует образу
  sha256 `349a900d…` (0.13-dev; полный хэш — в `docs/RELEASE.md`).

## 2026-11-18 · P9 (отчёт о загрузке на BOOT-раздел, без UART и SSH)

- В `board/r36s-v20/rootfs-overlay/etc/init.d/rcS` добавлен блок 7b: если `/flash`
  смонтирован, пишется `/flash/report/*` — `boot.txt` (дата, `uname -a`, cmdline, uptime),
  `mounts.txt`, `free.txt`, `dmesg.txt` (хвост 400 строк), `temps.txt` (все термозоны в °C),
  `cpufreq.txt` (cur/min/max/governor + GPU cur), `modules.txt`, `selftest.txt`
  (`launcher --selftest`). Любая строка — через `|| true`, отчёт не может сорвать загрузку.
- Зачем: у DEEPoS нет sshd, а UART-гребёнка требует паяльника/адаптера. FAT32 на BOOT
  читается с любого ПК: вынули карту — забрали отчёт.
- `tools/pull-report.ps1` (PowerShell 5.1, UTF-8 BOM): ищет том с меткой `BOOT`, копирует
  `report\*` в `build/device-report/`, печатает `boot.txt`, `selftest.txt`, `temps.txt`.
  Если тома нет — показывает список дисков с метками, чтобы не гадать.
- `tests/board_test.py::test_boot_report` — 14 проверок: каталог, guard `is_mounted /flash`,
  каждый файл, вызов `--selftest`, `sync`, best-effort на каждой строке записи.
- `flash-deepos.ps1`: ожидаемый sha256 больше не хардкодится — берётся из
  `docs/RELEASE.md` (`image sha256: ...`), иначе «unknown» и dpflash сверит сам.
- Сборка: rootfs OK, BOOT `0.14-dev`, образ sha256 `0e418a5f…` (полный — в `docs/RELEASE.md`),
  `PREFLIGHT: GO (32 checks)`, 16 наборов PASS.

## 2026-11-18 · P9 (USB-консоль и вердикт первого буста)

- `board/r36s-v20/rootfs-overlay/usr/local/bin/usb-gadget.sh`: configfs-gadget `deepos`
  с двумя функциями — `acm.gs0` (CDC-ACM → COM-порт на ПК) и `ncm.usb0` (сеть
  `<console-ip>/16`). Биндится к первому UDC, адрес ставится через busybox `ip`.
  Вызывается из `rcS` блоком 6b; без UART и без sshd даёт интерактивный root-шелл.
- `gadget-getty.sh` + строка в `/etc/inittab`: `ttyGS0::respawn:/usr/local/bin/gadget-getty.sh`
  (скрипт ждёт `/dev/ttyGS0`, затем `getty -L /dev/ttyGS0 115200`), чтобы не крутить respawn.
- `tools/usb-shell.ps1` находит COM-порт консоли (VID 1D6B / "USB Serial"), печатает команду
  `plink -serial COMx -sercfg 115200,8,n,1,N`; `tools/report-commands.sh` — готовый набор
  команд для неинтерактивного отчёта (uname, mounts, free, PSI, температуры, A/B, selftest, dmesg).
- `usr/local/bin/selfcheck.sh` → `BOOT/report/checks.txt` в формате `key=value`:
  `kernel`, `verdict`, `panel`, `input_events`, `battery`, `charger`, `flash`, `data`, `roms`,
  `modd`, `launcher`, `zram`, `swap_active`, `mem_total_mb`, `mem_available_mb`, `soc_c`.
  `verdict=FAIL`, если панель не connected или DATA не rw. `tools/pull-report.ps1` печатает
  checks.txt и предупреждает при FAIL.
- Найден баг в `flash-deepos.ps1`: проверка прав `IsInRole("Administrator")` на русской Windows
  возвращает False даже в elevated-окне (строка резолвится в локального пользователя, а группа
  называется «Администраторы»). Заменено на `[WindowsBuiltInRole]::Administrator` + фолбэк по
  SID `S-1-5-32-544`. Из-за этого скрипт отказывался писать при реальных правах администратора.
- Тесты: `tests/board_test.py` + `test_usb_gadget` (14 проверок) и `test_selfcheck` (16 проверок).
- Сборка: BOOT `0.16-dev`, образ sha256 `f5f1e3c865b045602db22e8c9effe68f1e544ca29751288941bfb0bda5711896`,
  `PREFLIGHT: GO (32 checks)`, 16 наборов PASS.

## 2026-11-18 · P7 (карта: безопасная идентификация размера диска, README в BOOT)

Прошивка упиралась в две вещи, обе закрыты тестами и повторным прогоном:

* **Размер raw-диска.** `dpflash.py` определял размер через `os.path.getsize`, а для
  `\\.\PhysicalDriveN` он отвечает `0` без исключения — скрипт останавливался с
  `target is 0 B`. Теперь нулевой результат не принимается, номер диска уходит в
  `Get-Disk -Number N`, размеры томов — в `GetDiskFreeSpaceExW`. Проверено: диск карты
  отдаёт 53 745 811 456 B, `--dry-run` на разреженном файле печатает `nothing written`.
* **README для владельца карты.** `board/r36s-v20/boot/README-FIRST.txt` попадает в BOOT
  через новый флаг `mkboot --extra` (файл копируется и учитывается в `MANIFEST.json`),
  в Makefile — цель `boot` с `BOOT_EXTRA`. В тексте — раскладка `ROMS/` по системам,
  где лежат `settings.toml` и `saves`, и что смотреть в `BOOT/report/checks.txt`, если
  экран остался чёрным.

Образ `0.17-dev`, 16 наборов зелёные, preflight GO, verify-image 39 проверок.

## 2026-11-18 · P8 (настройки редактируются с экрана)

Раньше экран «Настройки» только показывал значения из `settings.toml`. Теперь A на
карточках «Дисплей», «Звук» и «Питание» циклит значение, сохраняет файл и сразу
применяет: яркость и громкость шагами 20/40/60/80/100 %, профиль `eco → balanced →
max → eco`. Логика вынесена в `settings_edit_card()` в `apps/launcher/src/main.c`,
путь конфига по умолчанию выводится из `--data` (`<data>/config/settings.toml`), а не
захардкожен в `/data`. Заодно `row_count()` научился считать строки экранов
«Настройки» (12), «Модули» (5) и «Файлы» (6), иначе курсор не двигался.

`tests/settings_test.py` (10 проверок): циклы трёх карточек, сохранение комментария,
отсутствие `.tmp`, профиль рядом с модулями, `--config` и работа без sysfs.
17 наборов зелёные.

## 2026-11-18 · P5/P8 (демо-порт и первичное развёртывание)

Прошивка не содержит эмуляторов, поэтому проверить цепочку «библиотека →
`emulators.toml` → exec → fbdev → кнопки» на железе было нечем. Добавлен
`apps/playdemo` (60 строк): рисует кадр через те же `dp_canvas`/`dp_display`,
читает те же evdev-клавиши, UP/DOWN меняют столбики, B/START+SELECT выходят. На
хосте тот же бинарник пишет кадр в файл (`--fb frame.bin --keys ...`), поэтому он
покрыт тестом `tests/playdemo_test.py` (7 проверок).

Демо оформлен как обычный порт: `board/r36s-v20/rootfs-overlay/usr/share/deepos/roms/ports/demo.sh`
(`exec /usr/bin/playdemo "$1"`), в `emulators.toml` появилась строка
`ports = "/bin/sh %ROM%"`, а лаунчер теперь знает расширение `.sh` — папка
`/storage/ports` видна как система «Порты».

Первый буст сам готовит систему: `rcS` копирует `/usr/share/deepos/modules` в
`/data/modules` (иначе `modd` не стартует), `/usr/share/deepos/roms` в `/storage`
(там демо-порт), и применяет сохранённые яркость/громкость/профиль
(`launcher --apply --data /data`) до запуска UI. Проверки — в
`tests/board_test.py::test_rcs_provisioning`.

18 наборов зелёные, образ `0.19-dev`.

## 2026-11-18 · P1/P7 (паритет DTS со стоком, устойчивая запись карты)

Первая настоящая попытка прошить карту упала на `win32=21` (device not ready)
через двенадцать мегабайт: дешёвый картридер отваливается при потоковой записи.
`tools/dpflash.py` получил `write_retry()` — чанк пишется с переоткрытием
устройства (до 8 попыток, пауза 0.5–3 с), размер чанка снижен с 4 до 1 МиБ, а
после таблицы делается `verify_table()`: первые 34 сектора и хвост GPT читаются
обратно и сравниваются побайтово. `flash-deepos.ps1` перед записью делает
`Clear-Disk` — после сбоя Windows показывала на карте фиктивную «FAT16 на весь
диск», и без очистки тома снова блокировали raw-запись.

Главная находка раунда — `tests/hardware_test.py`: он декомпилирует наш DTB и
**стоковый дамп** (`tests/fixtures/stock-rf3536k3ka.dtb`, снят с самой консоли),
сопоставляет строки кнопок по контроллеру+пину, тайминги панели, reset-gpio и
проверяет, что драйверы собраны в ядро (`=y`), а не модулями. Тест сразу показал
**три потерянные кнопки**: в стоке 19 GPIO-линий (gpio3 10–27 плюс gpio2 13/14),
у нас было 16. Добавлены `key-aux1..3` (пин gpio3 27 и gpio2 13/14) и три линии
в pinctrl-группу; теперь наборы совпадают полностью.

Проверки: 19 наборов PASS, `PREFLIGHT: GO (32 checks)`, `verify-image: 39 checks`,
образ `0.20-dev` (4 294 967 296 B).

## 2026-11-19 · P1/P6 (корень найден: root=LABEL требует initramfs)

При разборе лога прошивки всплыла ошибка, которая убила бы первый буст: в
`extlinux.conf` стояло `root=LABEL=DEEPOS_A`. Разрешение LABEL делает initramfs
(или udev), а мы грузим ядро прямо с BOOT-раздела и initramfs не поставляем —
ядро упало бы в `VFS: Unable to mount root fs`. Теперь пишется устройство:
`root=/dev/mmcblk1p2` (слот A) и `root=/dev/mmcblk1p3` (слот B), `rootfstype=squashfs`.

`updatr` при `begin`/`switch` переписывает уже путь к устройству (плюс понимает
старые `root=LABEL=...` для совместимости со собранными ранее ботами), а
`preflight` и `board_test` теперь явно запрещают `root=LABEL=` — «нет initramfs»
стало проверяемым инвариантом, а не комментарием.

Побочно выяснилось, что пересборку образа нельзя делать, пока идёт запись:
второй запуск прошивки увидел новый sha256 в файле и корректно отказался писать
(`image sha256 does not match --expect-sha256`). Это правильное поведение, но в
чек-лист добавлено «не пересобирать образ во время записи».

Образ `0.21-dev`, 19 наборов PASS, preflight GO, verify-image PASS.

## 2026-11-19 · P7 (карта больше образа: GPT растягивается после записи)

Образ собран под 4 ГиБ, карта — 50 ГБ. Записанный как есть GPT описывал бы
4-гигабайтный диск: 45 ГБ остались бы недоступны, а раздел ROMS — 0.9 ГБ.
Добавлен `tools/expand_gpt.py`: после записи переносит резервную GPT в конец
устройства, растягивает последний раздел до `last_usable` и пересчитывает CRC.
`dpflash --expand` вызывает его сразу после таблицы, `flash-deepos.ps1` передаёт
флаг всегда — образ пересобирать не нужно.

По пути поймал собственную арифметику: массив записей GPT — это
`ENTRY_COUNT*ENTRY_SIZE` = 4096 Б = 8 секторов, а не 32, как в популярных
описаниях «34 сектора» (там 128 записей). Из-за этого `last_usable` уезжал на
24 сектора, и конец последнего раздела не совпадал с заголовком. Тест
`tests/expand_test.py` (11 проверок: перенос backup, CRC, совпадение конца
раздела с `last_usable`, неприкосновенность прочих разделов, отказ без GPT)
теперь это ловит.

20 наборов тестов PASS.

### 2026-11-19 · P7 (отчёт с карты без буквы диска)

Windows после raw-записи нередко не даёт BOOT букву диска, а отчёт буста нужен
именно оттуда. Добавлен `tools/read-report.py`: читает GPT прямо с устройства,
находит раздел BOOT, вытаскивает его во временный файл и копирует `report/`
через mtools; печатает `checks.txt` в консоль.

- `tools/read-report.py` (stdlib + mtools), флаги `--target`, `--out`, `--list`.
- `tests/read_report_test.py` (8 проверок): сборка образа, запись в файл,
  листинг, копирование, отсутствие отчёта даёт понятную ошибку, не падение.
- Образ `0.23-dev`: 4294967296 B, sha256 `43e8438055aec9548984a2c1a9343f822c0af230e7e9cb9a41d4c469eb1385f2`.
- Наборов тестов: 22.

### 2026-11-19 · P0 (карта не стартует: донорская boot-цепочка)

Консоль с прошитой картой не включается (чёрный экран, при зарядке горит
красный индикатор) — значит не запускается даже BootROM/U-Boot, а не ядро.
Отладить это на хосте нельзя, поэтому boot-область (32 KiB..16 MiB) взята из
эталонного образа Arch-R clone, который на этой плате стартует: `idbloader` +
U-Boot + служебные блоки копируются байт-в-байт, наш GPT и разделы остаются.

- `tools/import-loader.py --image build/deepos-r36s-v20.img --from-images ../images/ArchR-clone.img.gz`
- Образ `0.24-dev`: 4294967296 B, sha256 `0158ac69c0e71c504d989b915eedd69c454c0283a6dab5a41ff55acf0d18d195`; `verify-card` — PASS.
- Причина неудачи собственного `u-boot.itb`: у Arch-R на 8 MiB лежат
  служебные блоки `LOADER` и FIT-образы, а не FIT по адресу 0x800000, то есть
  их компоновка отличается от «idbloader + u-boot.itb по 8 MiB».


### 2026-11-19 · P0/P7 (загрузка V20 и проверка карты)

- Донорский Arch-R U-Boot запускает `boot.scr`. Сборка с `LOADER_DONOR` пакует скрипт DEEPoS, проверяет его CRC и SHA-256 и сравнивает загрузочную область с донором. Скрипт передаёт управление в extlinux, где аргументы ядра заданы одной строкой.
- GPT нового образа содержит 128 записей и взаимные адреса заголовков. ROMS заканчивается перед резервной GPT. Для чистой карты полный размер exFAT задаётся через `SIZE_MIB` при сборке.
- CI передаёт код завершения каждого набора тестов. Для прошивки Windows сверяет образ и выбранную карту до очистки и проверяет записанные байты.
- На тестовом Windows-картридере после `Clear-Disk` оставался тип GPT с нулём разделов. Прошивальщик допускает пустую разметку этого типа и проверяет обнуление таблиц чтением перед записью. Случай закреплён тестом обёртки.
- Образ `0.26-dev` записан на microSD с проверкой SHA‑256 содержимого и обеих GPT. После обновления кэша драйвера Windows видит GPT и все пять разделов. ROMS тестового образа занимает 931 118 592 байта. Запуск на самой V20 требует аппаратной проверки.

### 2026-11-19 · P0/P1 (профиль ядра Arch‑R для V20)

- На карте с чёрным экраном обе GPT, загрузчик, `boot.scr` и extlinux прошли проверку чтением. Отчёта загрузки нет.
- В старом DTB отключён VOP, а собранный Linux не поддерживает строку совместимости панели. Preflight проверяет эти условия и совпадение DTB в BOOT с подготовленным DTB.
- Тестовый профиль использует открытый Linux Arch‑R 6.12.114 и DTB EE Clone с оверлеем этой платы. Система и squashfs остаются DeepOS. Подробности в `docs/V20-BOOT-DIAGNOSIS.md`.

### 2026-11-19 · P7 (пустая MBR на новой microSD)

- После очистки MBR Windows может вернуть четыре записи с нулевой длиной и типом 0. Прошивальщик принимает их только при пустой таблице в первом секторе. Регрессионный тест сохраняет отказ для реального раздела.

### 2026-11-19 · P0/P1 (образ 0.33 для R36S‑V20)

- Сверка 0.32 с microSD прошла побайтово. В 0.32 отсутствовали оверлей 640×480 и обход встроенного `/init` Arch-R. Сборка 0.33 проверяет оба условия, использует фиксированный DTB V20 и пишет этап `sysboot` в BOOT.
- В оба системных слота включён модуль геймпада от того же ядра. Для V20 проверены коды крестовины, Select и физические A/B.
- Загрузчик сверяется с открытым донорским образом Arch-R. Инструкция сборки и контрольные признаки запуска записаны в `docs/V20-BOOT-DIAGNOSIS.md`.
- Windows-обёртка принимает обе проверенные microSD и образы в gzip. До очистки карты она проверяет размер и SHA-256 распакованных данных. Тесты покрывают запись gzip, отказ при повреждённом архиве или неверной контрольной сумме.

### 2026-11-19 · P0 (ранний UART на V20)

- На консоли 0.33 оставил этап `before_sysboot`. Убрана принудительная настройка раннего UART на 1 500 000 бод без его частоты. Preflight отклоняет эту комбинацию.
- BOOT проверочного образа 0.34 обновлён с резервной копией и проверкой SHA-256. Синий LED в этом варианте показывает инициализацию драйвера Linux.
- После 0.34 осталась метка 0.33. Для 0.35 восстановлен скрипт 0.33 и убрана старая метка после резервного копирования. Образ использует исправленный extlinux.

### 2026-11-19 · P0 (точка монтирования корня V20)

- С исправленным UART консоль дошла до журнала Linux. `panic=0` сохранил ошибку VFS на экране. Ядро нашло `DEEPOS_A` и получило `ENOENT` при монтировании.
- У встроенного initramfs Arch-R отсутствует `/root`. Сборка 0.37 создаёт дополнительный архив точки монтирования, добавляет его в extlinux и проверяет его содержимое до прошивки.
- На консоли 0.37 открыл меню. Отчёт BOOT вернул `PASS`: панель присутствует, launcher работает, зарегистрированы четыре устройства ввода.

### 2026-11-19 · P0 (первый успешный запуск 0.37 на R36S‑V20)

- microSD с образом 0.37 (`sha256 90cb6940…`, BOOT version `0.37-v20`) загрузилась до меню launcher. Чтение BOOT вернуло `version=0.37-v20`, `report/boot.txt` 436 B, `report/checks.txt` 223 B, `BOOTDIAG.TXT` 28 B.
- `checks.txt`: `verdict=PASS`, `panel=present`, `launcher=running`, `input_events=4`, `flash=rw`, `data=rw`. Это первый запуск, в котором ядро Arch‑R смонтировало корень DEEPoS без VFS panic.
- `BOOTDIAG.TXT` фиксирует последний этап U‑Boot `before_sysboot`; открывшееся меню доказывает, что дальше прошли sysboot, ядро, `/init` и handover в launcher.
- На устройстве отвечают крестовина влево/вправо и кнопки A/B. Отрисовка фокуса Up/Down и применение настроек кнопкой A требуют исправления — это следующая сборка, в проверенную 0.37 не входит.
- Образ записан на карту, прочитан обратно и сверен побайтово; геометрия BOOT (offset 16 MiB, 256 MiB) совпадает с образом.

### 2026-11-19 · P1 (0.38: ввод, навигация, читаемость интерфейса)

- Ввод переведён на выбор узла по возможностям: `EVIOCGBIT(0)`/`EVIOCGBIT(EV_KEY)` требуют `EV_KEY` и хотя бы одну стрелку; узел без них отклоняется, поэтому клавиатура больше не может занять место геймпада. Имя `r36s_Gamepad` осталось бонусом к выбору, а не единственным условием, и больше не переставляет A/B на этой плате.
- Автоповтор (значение 2) принимается только для стрелок: удержание крестовины листает списки, удержание A не запускает игру повторно. Ошибка или отключение узла (`POLLERR/POLLHUP`) выставляют `lost`, а launcher пишет причину в stderr вместо тихого выхода из цикла.
- Навигация стала двумерной и построчной: «Системы» 2 колонки, «Настройки» 3×4; ↑/↓ двигают по строке, ←/→ внутри строки, L1/R1 (и L2/R2) переключают вкладки. В «Играх» ←/→ меняют систему, A применяет настройку или запускает игру, B возвращает на уровень выше. На карточке «только просмотр» A показывает пояснение вместо молчаливого бездействия.
- Интерфейс: поднят контраст вторичного и третичного текста, выделение — фон `SEL` плюс полоса `ACC` 3 px, добавлены полосы прокрутки, строка подсказок с L1/R1 и реальные часы/батарея (батарея скрыта, если sysfs её не отдаёт). Экран «Инфо» показывает ядро, uptime, память, температуру, экран и устройство ввода; ошибки запуска и сообщения навигации выводятся тостом.
- Для будущего замера добавлены `--bench N` и файл-триггер `/flash/BENCH.ON`: устройство само прогоняет кадры отрисовки и до 20 нажатий, пишет `report/bench.txt` (запасной путь `/data/report/bench.txt`) со средним, p95 и максимумом времени отрисовки, вывода кадра и задержки «нажатие → кадр». На хосте 20 кадров: отрисовка в среднем 104 µs, p95 482 µs; вывод кадра и задержка на хосте не измеряются.
- Тесты: `run.py` (7 экранов, детерминизм, палитра по токенам темы, обновлённые эталоны), `input_test.py` (22 проверки, включая возможности, автоповтор и отказ клавиатуре), `display_test.py` (физические Right/Right/A меняют яркость 20→40), `launch_test.py` и `settings_test.py` — PASS. `verify-image.py` — 46 проверок.
- Собран образ 0.38: 4 GiB, `sha256 62fbcef2834e80a8ae5b0708a0705025395c27ad0817c0d0e6695b0183137632`. Загрузочная цепочка взята из проверенной 0.37 без изменений (`KERNEL` 19 449 864 B, DTB 72 915 B, `ROOTDIR.CPIO` 240 B, `boot.scr` 700 B, extlinux 737 B), новый только корень squashfs — 2 445 312 B (launcher 729 160 B).
- Образ записан на карту и прочитан обратно: SHA-256 образа и обе таблицы GPT совпали, карта видится как GPT с пятью разделами. Реальный замер на консоли остаётся за владельцем; тег 0.38 ставится после него.
### 2026-11-19 · P1 (0.38: чёрный экран и исправление загрузчика)

- Первая сборка 0.38 записана на карту, но консоль осталась с чёрным экраном — загрузчик не стартовал.
- Причина: образ собран без `LOADER_DONOR`, поэтому в область 32 KiB…16 MiB попал self-built `build/uboot` (`idbloader.img` 113 194 B). Рабочие 0.37 и донор Arch-R несут другой загрузчик: область idbloader `sha256 b72abb8b14f75b08`, область `u-boot.itb` `50b32959eb4c8f6d`. Для RK3326 нужен загрузчик донора; `make image-full` по умолчанию берёт `build/uboot`.
- Проверка показала, что BOOT-раздел обеих сборок побайтово совпадает (`KERNEL` 19 449 864 B, DTB 72 915 B, `ROOTDIR.CPIO` 240 B, `boot.scr` 700 B, extlinux 737 B, те же SHA-256 в MANIFEST), а rootfs — aarch64, статический, stripped. Единственная реальная разница — область загрузчика, поэтому чёрный экран дала именно она.
- Образ пересобран с `--loader-donor images/ArchR-clone.img.gz`; контрольные суммы обеих областей совпали с рабочим 0.37. Новый образ: 4 GiB, `sha256 5976a65e3556bfe1b2562f8b9dba15353a740368529b7f5436b6bb2670dad9ac`, `verify-image.py` — 43 проверки, PASS.
- В rootfs возвращён модуль `/lib/modules/6.12.114/archr-singleadc-joypad.ko` (40 136 B, SHA-256 совпадает с 0.37): сборка из main его не ставила, `rcS` грузит его необязательно, но без него теряются кнопки. squashfs — 2 457 600 B.
- Пустая карта после прошлых прогонов очищена `Clear-Disk`, образ записан заново и проверен чтением: `dpflash` в 17:01:14 подтвердил `verified: partition tables read back byte-identical`, `verified: image payload matches and the relocated GPT is intact`, `DONE: image written and verified` (exit 0). Карта 31 104 958 464 B, GPT, пять разделов.
- Запуск на консоли и реальный замер задержек остаются за владельцем; тег 0.38 ставится после него.

### 2026-11-19 · P1 (0.38: кнопки, поля экрана и вход по USB)

- Причина «мёртвых» кнопок: вендорский DTB отдаёт крестовину как `BTN_DPAD_UP/DOWN/LEFT/RIGHT` (0x220–0x223), а выбор узла ввода требовал `KEY_UP…KEY_RIGHT`. Теперь стрелки считаются по любому из двух наборов, узел `r36s_Gamepad` принимается, а A/B остаются на своих местах (`BTN_EAST`/`BTN_SOUTH`).
- Панель 640×480, но края закрыты корпусом. В тему добавлены безопасные поля сверху 8 px и снизу 12 px; строка состояния, заголовки, строки, прокрутка и подсказки сдвинуты внутрь, поэтому текст больше не уходит под пластик.
- Подсказки в «Системах» и «Настройках» дополнены `L1/R1 — вкладки`.
- Для отладки `rcS` поднимает `telnetd` на USB-NCM (`<console-ip>:23`): это временный вход в прототип, до релиза его нужно убрать.
- Тесты на хосте: `run.py` (7 экранов, палитра, обновлённые эталоны), `input_test.py` (22 проверки, включая вендорскую крестовину), `display_test.py`, `launch_test.py`, `settings_test.py` — ALL-PASS.
- `rootfs.squashfs` 2 457 600 B (launcher 729 160 B, модуль геймпада на месте), образ 4 GiB `sha256 f4ac57934093d04f52ad0e668a99e41f746c8c877a2afb16800189e337825d1a`, `verify-image.py` — 43 проверки, PASS.
- Первая запись на карту сорвалась на обратном чтении (`win32=1117`, ошибка устройства на 2.2 GiB) и оставила MBR; помог `diskpart clean`, повторная запись в 17:56:25 подтвердила таблицы и payload (`dpflash exit=0`).
- Рекомендации по эмуляторам собраны в `docs/EMULATORS.md`: минимум — RetroArch и семь лёгких ядер, тяжёлые (PSP/N64/DC/NDS) отдельным слоем; в образе эмуляторов пока нет.
- Логотип загрузки и реальный замер остаются следующими шагами; тег 0.38 ставится после замера.

### 2026-11-20 · P1/P4/P5 (0.39 V20, тестовая сборка)

- Увеличены битовые шрифты до 15/12 px, сохранён нативный кадр 640×480. Вывод учитывает каналы fbdev. Появились обратные переходы из настроек и экран проверки нажатий.
- Добавлены живые счётчики на вкладке «Сведения», запись настроек и применение лимитов CPU из доступных частот. Модули `thermal` и `saves` запускаются через POSIX sh. Создание копии сейвов выполняется без блокировки отрисовки.
- Комплект из Arch‑R включает RetroArch 1.22.2, 76 ARM64-ядер и 112 записей систем. Select + Start закрывает RetroArch через штатную комбинацию. Лаунчер заново открывает ввод и fbdev при возврате из игры.
- Хост-тесты пройдены. Под ARM64 проверены зависимости ядер и 120 кадров тестовой NES-программы. Прогоны на физической консоли предусмотрены в `DEVICE-TEST-PLAN.md`.

### 2026-11-20 · P1/P4 (терминальная тема 0.39)

- Добавлены зелёная палитра, выделение вкладок, шрифты Terminus 8×16 и 8×14 и три коротких сигнала ALSA, синтезируемых по запросу.
- Логотип рисуется из `rcS` сразу после появления fbdev. Лаунчер захватывает графический VT и ожидает готовность панели короткими повторными попытками. Первый кадр проверяется без событий ввода.
- Образ 0.39-v20-terminal записан на тестовую microSD после резервного копирования всех пяти разделов. Обратное чтение подтвердило совпадение данных образа и обеих таблиц GPT. Холодный старт и звук проверяются на консоли.

### 2026-11-20 · P4/P6 (настройки и USB в 0.40)

- Плитки настроек меняют звуки меню и параметры RetroArch. Переопределения пишутся в `/run` при старте игры. Добавлена подсказка ручной установки модулей.
- USB-сеть получает параметры по DHCP от хоста. USB-файлы временно отдаёт только размонтированный ROMS. Режимы запускаются по выбору пользователя, статус и ошибки выводятся в меню.

### 2026-11-20 · P4/P6 (модули, часы и TF2 в 0.41)

- Вкладка модулей сохраняет переключатель на DATA, открывает описание по Y и выполняет действие по X. Батарея, хранилище и эмуляторы собирают показания по запросу. Импорт через `ROMS/modules` начинается по кнопке A в окне установки.
- Регион выбирается из списка часовых поясов. Редактор даты и времени сохраняет UTC и обновляет часы консоли. При штатном выключении сохраняется последняя дата.
- TF2 определяется отдельно от карты системы и читается в `/games`. Список игр объединяет карточки систем и помечает источник игры. «Продолжить» учитывает TF2, в том числе при совпадении имён файлов.
- Добавлены проверки переключения модулей, закрытия окна описания, диагностики без фоновых процессов, сохранения даты и региона и запуска с правильной карты. Физическая проверка TF2 требуется на консоли.

### 2026-11-20 · P6 (PortMaster и расширенный комплект RetroArch)

- Опциональный ARM64-пакет PortMaster запускается из «Портов». Рабочий каталог сохраняется на DATA, портовые скрипты и игры на ROMS карты TF1. Bash, Python и SDL используются по запросу.
- Добавлен выбор установленного ядра по X в списках «Системы» и «Игры». Настройка системы действует для ROM на обеих картах. Профиль «Авто» возвращает команду из реестра.
- Инструмент сборки извлекает дополнительные ядра AArch64 из локального донора, сохраняет зависимости и формирует каталог вариантов.
- Старый Flycast 2021 убран из каталога из-за неразрешённого символа отрисовки. Существующие настройки с этим именем используют современный Flycast.

### 2026-11-20 · Свободные BIOS

- Добавлены EmuTOS 1.4 для Hatari и C‑BIOS 0.29a для картриджей blueMSX. Пакет включает лицензии, исходники EmuTOS и манифест SHA‑256.
- Установщик проверяет файлы и записывает отсутствующие, сохраняя пользовательские BIOS. Таблица путей построена по метаданным Libretro для ядер 0.41 bundle r2.
- Hatari и blueMSX загрузили тестовые носители и вывели кадры в ARM64-окружении. Проверены повторная установка и сохранение существующего файла.

### 2026-11-20 · 0.42: порты, GPU, zram и память

Всё найдено и проверено на живой консоли (DEEPoS 0.41-v20-test, ядро 6.12.114, USB-NCM + корневой шелл через порт `usb-shell.sh`).

- **Порты не стартовали из-за E2BIG.** `PortMaster/control.txt` экспортировал `SDL_GAMECONTROLLERCONFIG` длиной 474 120 байт (`gamecontrollerdb.txt` = 472 286 B). Одиночная строка окружения больше `MAX_ARG_STRLEN` (131 072) → каждый `execve` ребёнка падал с `Argument list too long`: в логах `NFSU1.sh` (`/bin/dd: Argument list too long`), `FlatOut 2.sh` (exit 126), `nfsu1.aarch64` — тот же текст. Решение: `usr/share/deepos/curate-controllerdb.sh` (busybox awk: whitelist контроллеров + кап 110 000 байт + строка `r36s_Gamepad`) вызывается из `run-port.sh` до `control.txt`; сборка пакета делает то же через `tools/curate-controllerdb.py`. После обрезки до 110 274 B порт дошёл до свопа и GL.
- **glibc-стабы.** В рантайме PortMaster glibc 2.40, где `libpthread`/`libdl`/`librt` слиты в libc, а бинарники портов их требуют. `install-portmaster.sh` создаёт симлинки `libpthread.so.0 libdl.so.2 librt.so.1 libutil.so.1 libresolv.so.2` на `libc.so.6`.
- **Sudo.** `control.txt` проверяет `sudo` и без него печатает «No sudo present.»; в rootfs добавлен шим `/usr/bin/sudo`, который отбрасывает флаги и выполняет команду (root и так есть).
- **GPU.** Mali-G31 собрана модулем: без `panfrost` нет `/dev/dri/renderD128` и любой GL падает с «EGL not initialized». Модули взяты из rootfs донора (`panfrost.ko`, `gpu-sched.ko`, `drm_shmem_helper.ko`) и грузятся в rcS до старта приложений; `GBM_BACKENDS_PATH=/usr/lib/gbm` с `dri_gbm.so` из донора. На консоли проверено: `panfrost ff400000.gpu: mali-g31 id 0x7093`, `Initialized panfrost 1.4.0`, порт NFSU1 дошёл до гостя (254 импорта, 22 806 функций).
- **zram.** zram не встроен, но собирается модулем: `zram.ko` требует `zsmalloc`, `lz4_compress`, `lz4hc_compress` и `zstd_compress` (иначе `insmod` даёт «Unknown symbol zstd_*»). rcS грузит набор, выбирает `lz4` до записи размера, даёт 512 МиБ swap с приоритетом 100, а файл на `/data` (256 МиБ, приоритет 10) остаётся холодным запасом. На консоли: Swap 924 МБ, `/proc/swaps` = два устройства.
- **RetroArch не запускался вообще.** `input_driver = "udev"` падал (`Couldn't open any keyboard…` → `Cannot initialize input driver`), `linuxraw` тоже; без `/usr/share/X11/xkb`. Рабочий вариант — `sdl2`: `GL context: "kms"`, шейдеры компилируются, `rc=0`. Проверено тестовым NES-ROM.
- **Прочее из списка консоли.** `hostname deepos` ставится в rcS (было `ArchR` при `/etc/hostname=deepos`); версия теперь берётся из одного файла `VERSION` (`0.42-v20-test`) и попадает в `os-release`, `/etc/deepos-version`, UI и MANIFEST; `/flash` монтируется с `sync` (FAT без журнала: `Volume was not properly unmounted`); `selfcheck.sh` пишет `gpu=` и `swap=`; порт-скрипт ищет слушателей в `/proc/net/tcp6` (там живут telnetd/httpd).
- **BIOS.** Новый `docs/BIOS.md` и `board/r36s-v20/data/bios-required.tsv` (27 позиций). `bios-check.sh` пишет `/flash/report/bios.txt` (`bios_ready=N/M`). В образе остаются только свободные EmuTOS и C-BIOS; проприетарные дампы пользователь кладёт сам в `/storage/bios` или `/games/bios`.
- **Тесты.** `tests/board_test.py` получил `test_gpu_and_ports_stack()` (модули и порядок, GBM, sudo, curate, `sdl2`, tsv, zram+swap, hostname, `sync`). `tests/ci/Dockerfile` — `alsa-lib-dev`, без него host-сборка лаунчера не находит `<sound/asound.h>`. Golden-хеш экрана «Сведения» обновлён: версия в UI изменилась.
- Полный набор (`run`, `modd`, `saved`, `modules`, `image`, `board`, `boot`) — PASS. Живая консоль: `ping`, порт-шелл и `httpd` переживают перезагрузку канала; образ 0.42 собран и записан в слот B.



### 2026-11-20 · 0.43: звук через класс-D и чистка сканера

Всё проверено на живой консоли (DEEPoS 0.42-v20-test, слот B, канал по USB-NCM).

- **Звук молчал из-за маршрута в дереве устройств.** Рабочий DTB (донорский) держит
  `rk817-sound-simple`: пин `Internal Speakers` идёт прямо на `SPKO`. DAPM включает `SPKO`,
  но не включает `Enable Class D` (R64 бит 0x80) и `Class D Mode` (R56 бит 0x10) — выход
  класса-D остаётся заглушённым, тон «играет» в никуда. Вторая карта в том же DTB
  (`rk817-sound-amplified`) ведёт усилитель `simple-audio-amplifier` от HPOL/HPOR: линия
  `enable` (gpio103) поднимается, а звука всё равно нет — класс-D обойдён.
  Решение: маршрут `Internal Speakers` → `SPK DAC`. Тогда DAPM тянет `Enable Class D`
  через цепочку питания, и тон 660 Гц слышен. DTB патчится `tools/dtb-sound-fix.py`
  (dtc внутри `deepos-build:boot-repair`), результат лежит в
  `board/r36s-v20/boot/dtbs/rk3326-r36s-v20.dtb` (sha256 848c361b…, 72 919 B), Makefile
  берёт его через `BOARD_DTB`/`KERNEL_DTB`. На консоли файл заменён в `/flash/dtbs`
  с бэкапами `/flash/dtbs/rk3326-r36s-v20.dtb.stock` и `/data/dtb-stock-backup.dtb`.
- **Диагностический инструментарий.** `rk817-reg.py` (i2c-dev: `get/set/or/and`) на консоли
  получает `EBUSY` — шину держит MFD RK8xx, поэтому регистры кодека читались только через
  `debugfs`: `/tmp/dbg/regmap/0-0020/registers` (`0x38 = 0x21`, `0x40 = 0x65`, то есть класс-D
  выключен), а состояние DAPM — `/tmp/dbg/asoc/rk817_ext/**/dapm/*`.
- **Сканер библиотеки считал `/storage/report` консолью «REPORT»** после того, как в отчётах
  остались `ra-probe.sh`/`ra-probe2.sh`. В `dp_scan.c` добавлен `is_reserved_folder()`
  (`bios`, `roms`, `modules`, `report`, `portmaster`, `saves`, `lost+found`); реестр расширений
  теперь можно подменить переменной `DP_EXTENSIONS` — это нужно тесту и отладке на ПК.
- **Тесты.** `tests/launch_test.py` проверяет `--roms <tmp> --list-roms`: `snes`/`ports` в
  списке, `report`/`bios` — нет. `tests/board_test.py` → `test_sound_route()`: исходник DTS и
  закоммиченный DTB обязаны содержать маршрут `Internal Speakers` → `SPK DAC`, в DTB не должно
  остаться маршрута на `SPKO`. Полный набор в контейнере — PASS.

## 2026-11-20 · 0.44: громкость на рокере, OSD и запас по уровню

Динамик зазвучал в 0.43 (маршрут через class-D), и сразу вылезли три вещи: на 100 % громкости
звук трещал, кнопки громкости не реагировали, а обратной связи на экране не было вообще.

- **Почему не реагировали.** Лаунчер открывал ровно один evdev-узел — геймпад
  
36s_Gamepad (event3). Рокер громкости висит на отдельном узле dc-keys (event1,
  KEY=c000000000000 0 → коды 114/115). Коды в map_code() были, но события до них не
  доходили. Теперь dp_input_open() дополнительно ищет узел с битами VOLUMEUP/VOLUMEDOWN
  (предпочитая имя dc-keys), хранит его в in->key_fd, а dp_input_poll() опрашивает оба
  дескриптора и отдаёт DP_KEY_VOL_UP/DOWN первым. При POLLHUP рокер закрывается, геймпад
  продолжает работать.
- **Почему не было видно.** Карточка «Звук» применяет значение, но никакого сообщения не
  показывала. Теперь после применения с 
av->volume_delta в 
av->notice уходит
  «Громкость N %» — это и есть всплывающее сообщение (toast) поверх меню.
- **Почему трещало.** dp_config_apply_volume() писал Master Playback Volume линейно:
  100 % → 255/255, а class-D на выходе кодека насыщается раньше. Шкала сжата до 84 %
  (use * 84 / 10000), проценты в меню остались прежними.
- **Громкость в игре.** В 
etroarch.cfg привязок громкости не было вообще. Добавлены
  input_volume_up = "keycode 115", input_volume_down = "keycode 114",
  input_volume_mute = "keycode 113", udio_volume = "-2.0" и menu_enable_widgets = "true"
  — полоска громкости рисуется средствами самого RetroArch, лаунчер в это время заблокирован
  на waitpid() и оверлей показать не может.
- **Тесты.** 	ests/board_test.py → 	est_volume_rocker(): код ввода ищет биты VOLUMEUP/DOWN
  и открывает второй узел с приоритетом dc-keys, шкала микшера содержит * use * 84 / 10000,
  лаунчер пишет olume_delta в 
otice, а 
etroarch.cfg содержит все четыре ключа и коды
  114/115. Полный набор в контейнере — PASS.

Ограничение на будущее: в портах (не RetroArch) громкостные кнопки обрабатывает сам порт —
SDL читает микшер один раз при старте, поэтому менять уровень во время игры в порту нельзя
без вмешательства в его код. Пока уровень выставляется до запуска и ограничен 84 % шкалы.

## 2026-11-20 · 0.45: кнопки громкости работают и внутри игры

В 0.44 рокер заработал в меню (надпись «Громкость N %»), но в игре кнопки молчали: лаунчер
запускает игру через `run_command()` и застревает в `waitpid()`, а свой цикл ввода к этому
моменту уже закрыт (`dp_input_close` перед `launch_selected`). Внутри игры единственным
источником обратной связи остаётся сам эмулятор.

- `apps/launcher/src/main.c`: добавлены `g_vol_config`/`g_vol_sysfs` (заполняются в `main()`
  после разбора `--config`), `volume_step(delta)` (читает `settings.toml`, ограничивает 1..100,
  пишет обратно и применяет к микшеру через `dp_config_apply_volume`) и
  `wait_with_volume(pid, &status)` — ожидание ребёнка с `WNOHANG` плюс `dp_input_poll()` на
  200 мс; на каждом нажатии `DP_KEY_VOL_UP/DOWN` уровень меняется на ±5. `run_command()` теперь
  ждёт через `wait_with_volume()`.
- Почему это работает: рокер живёт на своём evdev-узле (`adc-keys`), его можно открыть заново
  даже когда экран у игры; на ПК (тесты, CI) `dp_input_open()` возвращает ошибку, `armed = 0`
  и поведение остаётся прежним — блокирующий `waitpid()`.
- Ограничение, зафиксированное честно: полоски громкости внутри игры нет — фреймбуфером
  владеет игра, а `retroarch.cfg` (`input_volume_up/down`, привязки `keycode 128/129/127` и
  `volumeup`/`volumedown`) на этой сборке событий не получает: SDL2 отдаёт клавиатуру только
  окну в фокусе, и проверить это пробником с `SDL_VIDEODRIVER=dummy` невозможно (событий нет
  вовсе, даже кнопки A). Внутри игры уровень меняется, но без визуальной полоски.
- `VERSION` → 0.45-v20-test.

## 2026-11-20 · 0.46: буфер звука в портах и RetroArch

Пользователь проверил 0.44/0.45 на устройстве: звук появился, рокер работает и в меню (с надписью),
и внутри игры. Осталась одна проблема — треск в порте NFSU1 при 100 % громкости.

Что проверено на железе:

- Чистый тон 440 Гц через `audio-ctl.py tone` на том же уровне (214/255) звучит без треска —
  значит микшер и класс-D не клиппируют сами по себе.
- Порт при дефолтном буфере SDL трещит; с `SDL_AUDIO_DEVICE_SAMPLE_FRAMES=4096` треска меньше,
  с `8192` (≈170 мс при 48 кГц) — заметно меньше, но полностью не исчезает.
- Понижение микшера до 168/255 делает треск тише, но не убирает. Значит остаток — не клиппинг,
  а пропуски буфера: рекомпилированный порт занимает два ядра, и поток ALSA не успевает.

Сделано:

- `run-port.sh`: `export SDL_AUDIO_DEVICE_SAMPLE_FRAMES="${SDL_AUDIO_DEVICE_SAMPLE_FRAMES:-8192}"`
  (переменная остаётся переопределяемой для отладки).
- `retroarch.cfg`: `audio_latency = "128"` — тот же приём для эмуляторов.
- `tests/board_test.py`: `test_volume_rocker()` дополнительно требует наличие
  `SDL_AUDIO_DEVICE_SAMPLE_FRAMES` и `8192` в `run-port.sh`.

Честное ограничение: полного исчезновения треска это не гарантирует. Дальнейшие шаги, если
треск останется: 16384 кадров, затем проверка звука в RetroArch (если там чисто — виноват
именно порт), и как крайняя мера — потолок громкости 65 % шкалы.

## 2026-11-20 · 0.47: что взято у dArkOSRE для запуска игр

Разобрали официальную сборку dArkOSRE-R36 (форк ArkOS для R36S и клонов): в
репозитории только `files/BOOT` (ядро 12 МБ + паки DTB) и `files/ROOTFS`
(EmulationStation, Kodi, Drastic, RetroArch), образы ~3 ГБ раздаются через Mega/
Google/OneDrive. BIOS-дампов в сборке нет — как и ожидалось, их кладёт владелец.
Взяли оттуда то, что проверяемо и не ломает наш образ:

- **`audio_driver = "alsathread"`** вместо `alsa`. У нас ALSA писалась прямо в
  `retro_run()`, и на рекомпилированных портах (NFSU1 держит два ядра) запись не
  успевала: это и был остаточный треск после увеличения буфера. Плюс `sinc`
  ресемплер, `audio_out_rate = 48000`, `audio_rate_control`, `audio_sync`.
- **Threaded video**: `video_threaded = "true"`, `video_vsync = "true"`,
  `video_max_swapchain_images = "3"` — kmsdrm иначе блокирует ядро на весь вбланк.
- **Масштаб виджетов 2.5×** (`menu_widget_scale_auto = "false"`): на 640×480
  полоска громкости иначе занимала четыре пикселя — это к жалобе «нету
  отображения прибавления убавления звука».
- **Подъём частот вокруг запуска** — у них `perfmax/perfnorm` в каждом пункте
  `es_systems.cfg`. У нас CPU и так `performance`, а GPU жил на
  `simple_ondemand`, поэтому добавлен `usr/local/bin/perf-boost.sh on|off|state`
  (pins `ff400000.gpu` в `performance`) и обёртки в `run-port.sh` и
  `retroarch-game.sh` с `trap` на `EXIT INT TERM`.
- **Приоритет процесса**: `nice -n -5` для порта и для ядра (у них `-19`;
  взяли мягче, чтобы лаунчер с poll-циклом не голодал).

Не взяли: `input_driver = "udev"` (у них работает udevd, у нас проверенно `sdl2`),
`retroarch32` (32-битных ядер в импорте нет), `quit_press_twice`, `savestate_*`.
Отложено: заводские `spk-volume`, `hp-volume`, `spk-mute-delay-ms` и полярность
`hp-det` ACTIVE_LOW из их DTB для V20 — сначала проверяем эффект звуковых
настроек, DTB правим отдельным шагом (риск снова остаться без звука).

Тесты: `tests/board_test.py` получил проверки `alsathread`, `sinc`, threaded
video, виджетов 2.5, наличия и POSIX-ности `perf-boost.sh`, пиннинга governor,
подъёма/отката GPU и `nice` в обоих лаунчерах — 222 проверки `ok`, `PASS board`.
Версия: `VERSION` → `0.47-v20-test`.

## 2026-11-20 · 0.48: governor не остаётся запиненным

На живом прогоне порта под `timeout` обнаружилась дыра в 0.47: `timeout`
убивает обёртку SIGTERM'ом, busybox ash откладывает `trap` до возврата
дочернего процесса, поэтому `perf-boost.sh off` не выполнялся, GPU оставался на
650 МГц, и в этом состоянии система жила до перезагрузки. Замерено: во время
порта `governor=performance cur_freq=650000000`, через 40 с после `timeout 45`
— всё ещё `performance`, процесс `nfsu1.aarch64` тоже жив (его не убивают,
потому что убивали обёртку).

Что сделано:

- в `run-port.sh` и `retroarch-game.sh` рядом с `perf-boost.sh on` появился
  сторожевой фоновый подпроцесс: `( while kill -0 $$; do sleep 5; done;
  perf-boost.sh off ) &`. `$$` в подоболочке — pid обёртки, поэтому сторож
  снимает пиннинг и при нормальном выходе, и при `kill`/`SIGKILL` обёртки;
- `rcS` после загрузки модулей GPU вызывает `perf-boost.sh off`, чтобы
  запиненный governor не пережил перезагрузку (например, если консоль выключили
  во время игры);
- тесты: `run-port.sh restores the GPU when the wrapper is killed`,
  `retroarch-game.sh restores the GPU when the wrapper is killed`,
  `rcS resets the GPU governor at boot` — 225 проверок `ok`, `PASS board`.

Проверено на устройстве после заливки 0.47: `audio_driver = "alsathread"`,
`video_threaded = "true"`, `menu_widget_scale_factor = "2.5"` доехали,
`/usr/local/bin/perf-boost.sh` исполняемый, во время порта GPU на 650 МГц.
Версия: `VERSION` → `0.48-v20-test`.

## 2026-11-20 · 0.49: базовый конфиг RetroArch снова работает, threaded video убран

Проверка на устройстве вскрыла две ошибки 0.47.

1. **Настройки из `/usr/share/deepos/retroarch.cfg` не доезжали вообще.**
   `retroarch-game.sh` копировал базовый файл в `/storage/.config/retroarch/`
   только при первом запуске (`[ ! -e "$cfg" ]`), а там уже лежал вариант,
   созданный на первой загрузке 0.41. Дальше RetroArch запускался с
   `--config` этой копии, поэтому `audio_latency`, `sinc`, масштаб виджетов и
   даже `input_driver` из новых версий не применялись никогда. Теперь база идёт
   как `--config`, а пользовательская копия плюс хоткеи — сверху через
   `--appendconfig`; правки пользователя продолжают работать, а дефолты
   обновляются вместе с образом.
2. **`video_threaded = "true"` на этой плате не работает.** Вербозный лог:
   `[ERROR] [KMS] Error when switching mode` → `[ERROR] [Video] Cannot open
   threaded video driver. Exiting...` → `Fatal error received in:
   "video_driver_init_internal()"`. Ключ убран, остаются `video_vsync` и
   `video_max_swapchain_images`.

Звук: на чистом прогоне SNES-ядра (snes9x) звук слышен и кнопки работают —
значит тракт RetroArch → ALSA → класс-D исправен. Ядро fceumm с нашим NES-ROM
молчит; проверять дальше, это отдельная ветка (возможно, дамп ROM).
`audio_driver` оставлен `"alsa"` (измеренно рабочий), добавлен
`audio_device = "plughw:0,0"` — именно через plughw RetroArch открывает PCM
(FLOAT_LE, 48 кГц) и звучит; `alsathread` перенесён в отложенные эксперименты.

Тесты: 227 проверок `ok`, `PASS board`; добавлены проверки слоистого конфига,
`plughw`, отсутствия `video_threaded`. Версия: `0.49-v20-test`.

## 2026-11-20 · 0.50: управление, боковая громкость и темы

- В «Управлении» появился отдельный тест кнопок и четырёх осей. Физические `Select + Start` возвращают в настройки. Выбор стиков и перестановка A/B сохраняются для меню.
- Боковые клавиши применяют один шаг громкости в меню и во время игры. В меню показывается шкала. Ожидание служебных команд больше не перехватывает события контроллера.
- Добавлены 12 штатных тем, четыре компоновки библиотеки, предпросмотр и ограниченный формат пользовательских тем. Порядок создания и восстановления описан в [THEMES.md](THEMES.md).
- На ПК прошли 24 набора. ARM64-лаунчер прошёл `--selftest` в контейнере. Физический прогон кнопок, звука и игр требует рабочего USB-подключения к V20.

## 2026-11-21 · 0.51, геймпад в RetroArch и выход из игр

- При старте V20 DEEPoS добавляет в `/run` признак `ID_INPUT_JOYSTICK` для встроенного контроллера. Его имя, физический путь и номер устройства читаются из sysfs. RetroArch использует профиль `r36s_Gamepad` и назначает контроллер на порт 1. На плате проверено, что после Start NES-игра начинает передавать ненулевой сигнал в ALSA.
- RetroArch получает отдельные слои конфигурации. Поставляемая база, пользовательские параметры, системные хоткеи и параметры текущего запуска загружаются в таком порядке. Временный файл принадлежит одному запуску и удаляется при выходе.
- Лаунчер следит за Select + Start во время игры. Даёт эмулятору завершиться штатно и при необходимости завершает группу процессов игры. Выход подтверждён на плате в NES и NFS Underground. Тесты покрывают распознавание комбинации, одиночный Start и завершение дочернего процесса.
- [Аудит архитектуры V20](V20-ARCHITECTURE-AUDIT.md) содержит проверку каждого пункта настроек, результаты запусков, сравнение с другими прошивками и порядок развития общего механизма запуска.
- 0.51 установлена в B. После перезагрузки получены `verdict=PASS`, штатная регистрация геймпада и совпадение SHA‑256 считанного образа. Продолжение описано в [спецификации для следующего агента](V20-HANDOFF-SPEC.md).

## 2026-11-21 · Уточнение требований следующего раунда

- На работающей 0.51 чтение sysfs подтвердило активный предел `balanced` 1008 МГц. У модуля `thermal` обнаружена ссылка на отсутствующий `cpu-profile.sh`. Зафиксированы отдельные сценарии для карточки, модуля, загрузки и выхода из игры.
- В спецификации и стартовом промпте описаны прямой USB с условным резервом через ВМ, системный язык и шрифты, Fn, автосохранение при выходе и восстановление по всей матрице. Добавлена процедура актуализации спецификаций и результатов в конце каждого раунда.
