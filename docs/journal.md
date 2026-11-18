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

