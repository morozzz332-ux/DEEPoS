# Метрики DEEPoS

Заполняется после каждого сданного этапа. Пустое значение = не измерено (не «норма»).

| Дата | Этап | idle ОЗУ, МБ | MemAvailable, МБ | Загрузка до кадра, с | Демонов | SoC °C (4 потока) | FPS PSP-3D | Тесты |
|---|---|---|---|---|---|---|---|---|
| 2026-11-18 | baseline (Arch-R) | 263–318 | 414–468 | 20–30 | 7+ | 79.6 (1416 МГц) | 20–30 | — |
| 2026-11-18 | P0 launcher (host) | — | — | — | — | — | — | 7 экранов: PASS (1.0 с) |
| 2026-11-18 | P4b modd (host) | — | — | — | — | — | — | modd: PASS (0.64 с) |
| 2026-11-18 | P4c saved (host) | — | — | — | — | — | — | saved: PASS (0.15 с) |
| 2026-11-20 | 0.39 V20 (host) | — | — | — | — | — | — | 23 набора тестов, включая fbdev, evdev, настройки и запуск |

В проверочном комплекте RetroArch 76 ARM64-ядер и 112 команд для систем донора.
Распакованный комплект занимает около 933 МиБ на DATA. Все 76 ядер прошли
проверку загрузчиком AArch64 на разрешение динамических библиотек. Тестовая
NES-программа прошла 120 кадров в FCEUmm под эмуляцией ARM64 с отключёнными
видео и звуком. ОЗУ, загрузку, термику и FPS на V20 нужно замерить на устройстве.

Терминальная сборка 0.39, ARM64. Секция программы и констант лаунчера по
`size` уменьшилась с 884 361 до 881 537 Б. `data` и `bss` составили 25 792 и
25 292 Б соответственно. Буфер кадра остаётся 614 400 Б. Звуки используют
до 6 КиБ PCM на стеке короткоживущего процесса. RSS проверяется на V20.

Сборка 0.40. Хост-тесты проходили с новыми настройками RetroArch и
проверками USB-скриптов. DHCP-клиент запускается только в режиме USB-сети.
Фактические RSS, скорость передачи и время получения адреса измеряются на V20.

Дополнительно, P0 (host-сборка, `deepos-build:local`):

- бинарь лаунчера: **58 376 B** (`apps/launcher/launcher`, `-O2` aarch64/x86-64 без внешних зависимостей);
- рендер 7 экранов (`tests/ci/render-all.sh`): **2 516 мс** на alpine-контейнере (включая создание 1 901 файла фикстур);
- прогон тестов (`tests/run.py --no-build`): **993 мс**;
- golden-хэши: 565 B (`tests/golden/hashes.json`), 7 записей;
- шрифты: 181 глиф × 2 размера (13/17 px box, 11/14 px box), `dp_font.c` 28 869 B + `dp_font_small.c` 24 585 B.
- P4b+ modules (host): thermal + saves protocol, helpers, modd handshake, rotation — PASS (python3 tests/modules_test.py)
- P3/P7 image (host): GPT/FAT32/squashfs/ext4/exFAT + flash lossless — PASS (python3 tests/image_test.py, test image 128 MiB)
- P0/P1 board (host): DTB 9 316 B, dtc+kernel/busybox configs+extlinux+rootfs builder — PASS (python3 tests/board_test.py, 306 мс)- P6/P7 boot (host): mkboot layout/manifest + A/B attempts/rollback — PASS (python3 tests/boot_test.py)
- P1 kconfig (6.12.56, host): 113/113 fragment symbols satisfied, 0 unknown — PASS (sh tools/kconfig-check.sh)
| P0 kernel | build-kernel.sh | Image + DTB из исходников, BUILD.txt с sha конфига |
| P3 rootfs | build-rootfs.sh | squashfs 1.87 MB, 439 entries, static busybox + 3 apps |
| P0 kernel | 6.12.56 aarch64 | Image 74.5 MB, DTB 46.6 KB, config 113/113 |
| P3 image | mkimage 4096 MiB | 4 296 015 872 B, sha256 19130fdb…, 5 partitions |
| P0 uboot | vendor next-dev | idbloader 113 194 B, itb 1 304 064 B |
| P3 image-full | 4096 MiB + loader | 4 311 744 512 B, sha256 cabbf277… |
| P6 updatr | host build | 21 checks PASS, A/B + install |
| P4 input | host | 17 checks PASS, evdev-независимая навигация |
| P4 launcher↔modd | host | 6 checks PASS, живой список модулей |
| P4 display | host | 8 checks PASS, RGB565 blit = PPM |
| P4b module action | host | launcher→modd→module, 2 checks |
| P4 image | host | 4 311 744 512 B, sha256 e9a1d010… |

| P4/P7 launch pipeline | 12 проверок `launch_test.py`, hook allow/deny, `%ROM%`-подстановка | PASS |
| image (0.2-dev) | `build/deepos-r36s-v20.img` 4 311 744 512 B, sha256 `7b403aa9e80c0fc71e5df8c8232aa8a518a343fd1c421dc05b3063e1adfe0a6c` | ok |

| launch slot | `--save-slot N` + `%SLOT%`, проверено заглушкой | PASS |
| DATA content | `debugfs` читает файл из раздела DATA тестового образа | PASS |

| P4 continue-launch | host | `launch_test.py` 14 проверок, ROM+слот из `continue.tsv` |
| image (0.4-dev) | `build/deepos-r36s-v20.img` 4 311 744 512 B, sha256 `2998da9941c4820c293577a0f1eadb5b5fb12d4e5da556d3a03ab52390450372` | ok |

| P4 selftest | host | 1 набор, контракт `ключ=значение` + пустое окружение |
| image (0.4-dev) | `build/deepos-r36s-v20.img` 4 311 744 512 B, sha256 `f19cc4ad9bdee3c564d5c3e887575144a1800b3d95788dedd0af36a7db6e579f` | ok |
| тестовые наборы | 13 (screens, selftest, input, display, launcher+modd, board, image, modd, saved, modules, boot, updatr, launch) | PASS |

| P4 continue update | host | строки: 7 колонок, слот, `has_save`, без дублей и `.tmp` |
| image (0.4-dev) | `build/deepos-r36s-v20.img` sha256 `3701b7211369ad273220662282c82ca7a43049ab217f9a4b654e2663e557f93f` | ok |

| P6/P7 A/B (extlinux) | host | `begin`/`switch` переписывают `root=LABEL=DEEPOS_A|B`; rollback после 4-й неудачи | ok |
| rcS порядок | host | `/flash` смонтирован, `begin`/`good` до `exit 0` | ok |
| image (0.5-dev) | `build/deepos-r36s-v20.img` 4 311 744 512 B, sha256 `4f921aa551cc1020d9ffc9e5e4625bb81c2f97d1f4c78a0878db8bc4e2e14dc7` | ok |
| тестовые наборы | 13 | PASS |

| P7 verify-image | host | 39 проверок: GPT CRC, геметрия, сигнатуры ФС, загрузчик, BOOT, squashfs | PASS |
| image (0.5-dev) | `build/deepos-r36s-v20.img` 4 294 967 296 B, sha256 `6cf5a8be2ab34f037763a49a152525662b5974f7355347e61304a4fc9166ecf7` | ok |
| тестовые наборы | 13 | PASS |

| P8 config (host) | `tests/config_test.py` | 18 проверок: дефолты, save/load, отказы, sysfs apply, битый файл | PASS |
| образ (0.6-dev) | `build/deepos-r36s-v20.img` 4 294 967 296 B, sha256 `505f1c6b9a620542e72e173a9528fcae4988deeeb4dd43bed960af7b67eda518` | ok |
| наборы тестов | 14 | PASS |

| P0 mounts (host) | `tests/board_test.py` | 7 проверок привязки разделов p1/p4/p5 и путей модулей | PASS |
| образ (0.7-dev) | 4 294 967 296 B, sha256 `2569c4b70f510d562d31198d272ae321a6e81a3ad65cf7aa1f50cead38916fd7` | ok |

| P0 rcS (host) | `tests/board_test.py` | 13 проверок: best-effort mounts, mount_part, /data/config, guard A/B, sh -n | PASS |
| образ (0.8-dev) | 4 294 967 296 B, sha256 `bf04b4dbf32d3d9bcfabaa41ab71f179c0a36916bbb02ddd9af5eedc1f16b6c5` | ok |

| P0 handover (host) | `tests/board_test.py` | 8 проверок: readiness-строка, respawn лаунчера, overlay, exec-бит | PASS |
| образ (0.9-dev) | 4 294 967 296 B, sha256 `95227b2595af00cc7ba07359f8edc360cd3a2c856505f6b743f1a83f85c51429` | ok |

| P8 empty-state (host) | `tests/run.py` | подсказки на пустой библиотеке (systems/continue) | PASS |
| образ (0.10-dev) | 4 294 967 296 B, sha256 `04e5df4738e8db991dd98aabab8c77d2c716d13036d5c0f845e47e90bb7a83bc` | ok |

| P8 settings UI (host) | `tests/run.py` + `tests/selftest_test.py` | карточки читают settings.toml, selftest печатает config | PASS |
| образ (0.11-dev) | 4 294 967 296 B, sha256 `f5bdb6c1a59070c319af6dc1da50181e56ebf1f676c532453ddf442341ccdd9e` | ok |

| P8 files screen (host) | `tests/run.py` + `tests/selftest_test.py` | состояние разделов и свободное место в UI | PASS |
| образ (0.12-dev) | 4 294 967 296 B, sha256 `e8e4273a7ba7e3ec269c3b2d3bbaedfdfd19b1acee349bf08bd3db6d5a5ccfd3` | ok |
| P7 preflight (host) | `tools/preflight.py --root .` | 32 проверки, PREFLIGHT: GO | PASS |
| P7 preflight test | `tests/preflight_test.py` | GO/NO-GO на синтетике (missing fdt, missing launcher) | PASS |
| P8 render timings (host) | `tests/ci/measure.py` | 7 экранов: 9.4–10.7 мс/кадр, бинарь 85 208 B | PASS |
| образ (0.13-dev) | 4 294 967 296 B, sha256 `349a900d6b318888851e35a2260893db2b7eadfb4ec99e08b194935e0d4bf2c3` | UART getty + passwd | ok |
| release report | `docs/RELEASE.md`, 7 артефактов, git `main` | `tests/release_test.py` | PASS |
| boot report | `/flash/report/*` (8 файлов), `tools/pull-report.ps1` | `tests/board_test.py` | PASS |
| образ (0.14-dev) | sha256 `0e418a5f8920679d807c936ba5499d8c1fa417d3678e89b50caef4cf67cea07a` | сборка + preflight | GO |
| usb gadget | ACM + NCM, `usb0` <console-ip>/16 | `tests/board_test.py` | PASS |
| selfcheck | `BOOT/report/checks.txt`, 16 ключей | `tests/board_test.py` | PASS |
| образ (0.16-dev) | sha256 `f5f1e3c865b045602db22e8c9effe68f1e544ca29751288941bfb0bda5711896` | preflight + 16 наборов | GO |

## 2026-11-18 · образ 0.17-dev

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 16 |
| preflight | GO (32 checks) |
| verify-image | PASS (39 checks) |
| Образ | `build/deepos-r36s-v20.img`, 4 294 967 296 B, sha256 `05598792dd1dd795fa332f467884903721f0c4ffd3d979659675d676ed70a2fe` |
| BOOT | `0.17-dev`, KERNEL 74 490 368 B, dtb 46 564 B, `README-FIRST.txt` 1 533 B |

## 2026-11-18 · образ 0.18-dev

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 17 |
| preflight | GO (32 checks) |
| verify-image | PASS (39 checks) |
| Образ | 4 294 967 296 B, sha256 `02cff0cfb53563dcd7f2e4e09a29298ca06928818ec61510c36c1072806359ce` |

## 2026-11-18 · образ 0.19-dev

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 18 |
| playdemo (static aarch64) | 597 944 B |
| preflight / verify-image | GO (32 checks) / PASS (39 checks) |
| Образ | 4 294 967 296 B, sha256 `c824889e9138e7f9aa1ec9e76aa9e17ea598250c86bcd35fe90ae2e16f65f6cd` |

## 2026-11-18 · образ 0.20-dev

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 19 |
| Кнопочных GPIO-линий | 19 (паритет со стоковым DTB) |
| DTB | 46 836 B |
| preflight / verify-image | GO (32) / PASS (39) |
| Образ | 4 294 967 296 B, sha256 `4a647723d8d493a879ef28e0e7d46b39f76864fd26d43dcb675aae07649029cf` |

## 2026-11-19 · образ 0.21-dev

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 19 |
| Корень системы | `/dev/mmcblk1p2` (A) / `p3` (B), без initramfs |
| preflight / verify-image | GO (32) / PASS (39) |
| Образ | 4 294 967 296 B, sha256 `84cdb21a2432369d70f6fc4e3910970c099e721e60611305a800cc899586dfc2` |

## 2026-11-19 · расширение карты

| Проверка | Значение |
| --- | --- |
| Наборов тестов | 20 |
| ROMS после expand (50 ГБ карта) | ~45 ГиБ вместо 0.9 ГиБ |
| backup GPT | последний сектор устройства, CRC сходится |
- 2026-11-19 · образ `0.23-dev` — 4294967296 B, sha256 `43e8438055aec9548984a2c1a9343f822c0af230e7e9cb9a41d4c469eb1385f2`; тестовых наборов 22; verify-image 39 проверок; preflight GO (32).
- 2026-11-19 · образ `0.24-dev` (донорская boot-цепочка) — 4294967296 B, sha256 `0158ac69c0e71c504d989b915eedd69c454c0283a6dab5a41ff55acf0d18d195`; verify-card PASS.

## 2026-11-19 · образ 0.33 для R36S‑V20

| Проверка | Результат |
| --- | --- |
| Наборы тестов хоста и Windows | 23 набора хоста и обёртка прошивки прошли |
| preflight / verify-image | GO (36) / PASS (41) |
| Файловые системы | GPT и FAT32 прошли проверку, оба слота содержат точную копию модуля геймпада |
| QEMU ARM64 | Оба squashfs-слота монтируются, запускаются BusyBox init и launcher |
| Полевые замеры | Время запуска, память, температура и FPS проверяются на R36S‑V20 |

- 2026-11-19 · На microSD образ 0.33 прошёл контрольное чтение и проверку GPT. На консоли получен этап `before_sysboot`.
- 2026-11-19 · Проверочный образ 0.34 прошёл preflight (36), проверку образа (41) и контрольное чтение обновлённых файлов BOOT.
- 2026-11-19 · 0.35 прошёл preflight (36), проверку образа (41) и контрольное чтение обновлённых файлов BOOT.
- 2026-11-19 · На R36S‑V20 0.35 вывел журнал Linux, а 0.36 удержал сообщение о VFS panic. 0.37 добавляет точку монтирования и прошёл preflight (38), проверку образа (43) и контрольное чтение BOOT.
- 2026-11-19 · Физический запуск 0.37: меню открывается, `verdict=PASS`, `input_events=4`, BOOT и DATA доступны на запись.

## 2026-11-19 · первый запуск на R36S‑V20 (0.37)

| Проверка | Результат |
| --- | --- |
| Загрузка до меню | да, launcher отрисовал первый кадр |
| Отчёт BOOT | `verdict=PASS`, `report/checks.txt` 223 B, `report/boot.txt` 436 B |
| Панель | `panel=present` |
| Ввод | `input_events=4` (четыре устройства) |
| Разделы на запись | `flash=rw`, `data=rw` |
| Последний этап U‑Boot в `BOOTDIAG.TXT` | `before_sysboot` |
| Время до первого кадра | не измерялось |

## 2026-11-19 · ввод, навигация и читаемость интерфейса (0.38)

| Проверка | Результат |
| --- | --- |
| Сборка launcher/playdemo для aarch64 | без предупреждений, `-Werror` |
| Хостовые наборы | `run`, `input`, `display`, `launch`, `settings` — PASS |
| Проверка образа | `verify-image` PASS, 46 проверок |
| Разметка карты | GPT, 5 разделов: BOOT / DEEPOS_A / DEEPOS_B / DATA / ROMS |
| Запись и обратное чтение | SHA-256 образа и обе таблицы GPT совпали |
| Замер на хосте | 20 кадров: отрисовка avg 104 µs, p95 482 µs |
| Замер на железе | ожидает владельца, триггер `/flash/BENCH.ON` готов |

- 2026-11-19 · Ввод выбирает узел по `EVIOCGBIT` (стрелки + `EV_KEY`), принимает автоповтор только для стрелок и сообщает о потере устройства.
- 2026-11-19 · Сетки «Системы» и «Настройки» навигируются построчно; L1/R1 переключают вкладки, A применяет настройку только на редактируемых карточках.
- 2026-11-19 · Образ 0.38 (`sha256 62fbcef2…`) прошит на карту и сверен обратным чтением; загрузочные файлы BOOT идентичны проверенной 0.37, новый только squashfs корня.
## 2026-11-19 · 0.38 после исправления загрузчика

| Проверка | Значение |
|---|---|
| Загрузчик | области idbloader/u-boot совпадают с донором Arch-R |
| verify-image | 43 проверки, PASS |
| image sha256 | `5976a65e3556bfe1b2562f8b9dba15353a740368529b7f5436b6bb2670dad9ac` |
| rootfs.squashfs | 2 457 600 B, модуль геймпада на месте |
| Запись на карту | dpflash: таблицы и payload прочитаны обратно, exit 0 |
| Запуск на консоли | ожидает владельца |

- Чёрный экран первой 0.38 был вызван сборкой без `LOADER_DONOR` (self-built `build/uboot` вместо вендорского загрузчика донора).
- BOOT, ядро, DTB и initramfs не менялись: их SHA-256 совпадают с рабочей 0.37.

## 2026-11-19 · 0.38: кнопки, поля и отладка по USB

| Проверка | Значение |
|---|---|
| Узел ввода | `r36s_Gamepad`, крестовина `BTN_DPAD_*` принята |
| Безопасные поля | сверху 8 px, снизу 12 px |
| Тесты на хосте | ALL-PASS (run/input/display/launch/settings) |
| rootfs.squashfs | 2 457 600 B |
| image sha256 | `f4ac57934093d04f52ad0e668a99e41f746c8c877a2afb16800189e337825d1a` |
| verify-image | 43 проверки, PASS |
| Запись на карту | dpflash: таблицы и payload прочитаны обратно, exit 0 |
| Вход для отладки | telnet `<console-ip>:23` (временный, убрать до релиза) |
| Запуск на консоли | ожидает владельца |

## 2026-11-20 · 0.41: модули, время и TF2

| Проверка | Результат |
|---|---|
| Тесты на хосте | Все сценарии `tests/run-all.sh` прошли |
| Диагностические модули | 0 запусков при старте игры, процессы завершены после сбора показаний |
| Размер squashfs | 2 592 768 байт, на 28 КиБ больше 0.40 |
| Запись на microSD | Обратное чтение `DEEPOS_A` совпало с собранным squashfs |
| ROMS на тестовой карте | 25,83 ГиБ, exFAT, 136 стандартных каталогов |
| ОЗУ, время загрузки, RTC и чтение TF2 | Требуется замер на консоли |

## 2026-11-20 · Расширенный пакет 0.41

| Проверка | Результат |
|---|---|
| Размер squashfs r2 | 130 551 808 байт |
| Ядра AArch64 | 118 доступных, включая 43 дополнительных и замену EmuSCV |
| ARM64-проверка | Загрузка 118 ядер, CLI PortMaster и обнаружение SDL KMSDRM |
| Тесты на хосте | 22 набора, включая настройку ядра для системы |
| Запись r2 на microSD | Прочитанный обратно системный слот совпал с squashfs |
| Реальный экран PortMaster, геймпад и FPS | Требуется замер на консоли |

## 2026-11-20 · 0.50, управление и оформление

| Проверка | Результат |
| --- | --- |
| Наборы `tests/run-all.sh` | 24 завершились с кодом 0 |
| Время рисования на ПК, p95 по 120 кадрам | 78 мкс «Терминал», 85 мкс «Зона», 88 мкс «Ночной гараж» |
| Rootfs с PortMaster и дополнительными ядрами | 130 834 432 байта, на 4 096 байт больше 0.49 |
| ARM64 launcher `--selftest` в контейнере | `status=ok` |
| RSS, задержка ввода, звук и запуск игр на V20 | Требуется проверка на консоли |

## 2026-11-21 · Замеры на V20 и проверка 0.51

| Проверка | Результат |
| --- | --- |
| DEEPoS 0.50, меню в покое | RSS лаунчера 2840 КиБ, около 611 МиБ доступно системе, PSI `full avg10=0` |
| ARM64, проверка загрузки библиотек ядер | 118 из 120, включая работающие замены двух старых сборок |
| ARM64, запуск образцов игр | 17 из 21 достигли 120 кадров с пустыми видео- и аудиодрайверами |
| NES, регистрация встроенного геймпада | RetroArch назначил порт 1, после Start игра начала выдавать ненулевой аудиосигнал |
| NES, ALSA 48 кГц, три прогона по 20 секунд | `EPIPE` 6 при 128 мс, 2 при 192 мс, 6 при 128 мс и более дешёвом sinc |
| NFS Underground, контрольный прогон | 4096 кадров при 44,1 кГц, 0 зарегистрированных `EPIPE` |
| Select + Start на V20 | Возврат в меню из NES и NFS Underground |
| DEEPoS 0.51 после перезагрузки в B | SHA‑256 совпал с собранным образом, `checks.txt` PASS, геймпад зарегистрирован при загрузке |
| DEEPoS 0.51, меню в покое | RSS лаунчера 2828 КиБ, 624 468 КиБ `MemAvailable`, PSI `full avg10=0` |
| DEEPoS 0.51, чтение профиля питания | `balanced` в `settings.toml` и `/data/cpu-profile`. `policy0` в `performance`, минимум 408 МГц, текущая и максимальная 1008 МГц. Плата сообщает OPP 408, 816, 1008, 1296 МГц. Переключение всех профилей в этом раунде не выполнялось. |

## 2026-11-21 · 0.52, проверки на хосте (консоль выключена)

| Проверка | Результат |
| --- | --- |
| Наборы `tests/run-all.sh` в `deepos-build:local` | 23 набора PASS, 0 провалов; `matrix_test.py` — 235 проверок |
| Сборка лаунчера | `launcher` с `dp_power` собрался без предупреждений под `-Wall -Wextra -Werror -pedantic`; отдельного замера размера в этом раунде не снимали |
| Питание, фикстура `408/816/1008/1416/1512` | `eco` → 816 000, `balanced` → 1008 000, `max` → 1 416 000 (OPP 1296 в фикстуре нет; правило потолка), повтор → `unchanged` |
| Питание, пол 1008 000 при `eco` | `applied`, минимум снижен до 816 000, оба файла равны 816 000 |
| Питание, пустой sysfs | `unsupported`, причина `нет cpufreq в <prefix>` |
| Игровой сеанс, возврат лимита | Заглушка поднимала максимум до 1 416 000, после выхода вернулось 1 008 000, снимок удалён |
| Устаревший снимок питания | Восстановлен при старте меню, файл потреблён |
| Модуль `thermal`, root-помощник | Реально пишет 816 000, статус `applied`/`eco`/816 000/`schedutil` |
| Размер матрицы | 175 строк, 127 установленных маршрутов, 15 предложенных, 33 без маршрута, 40 невидимых лаунчеру |
| Запись запуска | `last-launch.tsv` содержит систему, ROM, карту, рантайм, ядро, слот, код выхода и сигнал; после сигнала 15 поле `signal=15`, после кода 3 — `exit=3`; неразрешённый маршрут файл не меняет |
| Замеры на V20 | Выполнены 21.11.2026 на установленной 0.51 с проверочным бинарником `/data/launcher-052`; см. таблицу ниже |

## 2026-11-21 · 0.52, проверки на V20 (консоль подключена)

| Проверка | Результат |
| --- | --- |
| Доступные OPP `policy0` | `408000 816000 1008000 1296000` — 1416 и 1512 на этой ревизии отсутствуют |
| Исходное состояние | `performance`, минимум 408 000, текущая и максимальная 1 008 000; GPU `simple_ondemand`, 200 МГц из 650 |
| `--set-power eco` / `balanced` / `max` | `applied`, `scaling_max_freq` и `scaling_cur_freq` = 816 000 / 1 008 000 / 1 296 000; повтор того же профиля → `unchanged уже 816000` |
| `--apply` (путь rcS) при уже применённом профиле | `applied=1`, `power unchanged`, `brightness=100 volume=85 profile=balanced` |
| Запись лимита драйвером | Асинхронная (workqueue): немедленное чтение отдаёт старое значение. Подтверждение опросом 25×10 мс; без него успешная запись ложно считалась `error` |
| Игровой сеанс-заглушка | Ребёнок поднимал максимум до 1 296 000 и GPU governor в `performance`; после выхода 0, кода 3 и `SIGTERM` вернулись 1 008 000 и `simple_ondemand`, снимок удалён, `last-launch.tsv` — `exit`/`signal` соответствуют |
| Устаревший снимок на старте меню | Максимум 1 296 000 возвращён к 1 008 000, файл потреблён |
| Отложенный запрос модуля | Применён при старте меню: `eco` → 816 000, статус `applied`, запрос удалён |
| Помощник `thermal-apply.sh` на реальном sysfs | `max` → 1 296 000, `balanced` → 1 008 000, `eco` → 816 000; статус `applied` с причиной и `governor=performance`, `gpu_max_hz=650000000`, запрос удалён; `turbo` отклонён с кодом 2 |
| Перезагрузка с проверкой после неё | Не выполнена: после `reboot` USB-гаджет не перечисляется без переподключения кабеля |

## 2026-11-21 · 0.52, собранный образ и установка в слот A

| Проверка | Результат |
| --- | --- |
| Версия | `VERSION` = `0.52-v20-test`, внутри образа `etc/deepos-version` = `0.52-v20-test` |
| Наборы `tests/run-all.sh` | 24 набора PASS, 0 FAIL (добавлен `session_lock_test.py`) |
| Голдены кадров | Изменилась одна строка `info` (в кадре «Сведения» есть версия); обновлена через `run.py --update` |
| Образ rootfs | `build/deepos-rootfs-0.52-v20-test.squashfs`, 130 842 624 B, sha256 `837e00f71e04cad140c562f11bdfd84364056062ad029a9bae593c2bb605af7c` |
| Установка в A | `updatr install` записал 130 842 624 B, обратное чтение раздела дало тот же sha256; `switch A` — `root=PARTLABEL=DEEPOS_A`, generation 5 |
| Загрузка после `reboot -f` | Консоль вернулась без переподключения кабеля; версия 0.52, слот A, `attempts=0`, `rollback=false` |
| `launcher --selftest` на 0.52 | `status=ok`, `fb=/dev/fb0`, `fb_present=1`, `input_events=4`, `input=r36s_Gamepad` |
| Память и PSI после загрузки | `MemAvailable` 652 836 kB из 749 580 kB, `PSI some avg10=0.00` |
| Повторная загрузка 0.52 | Снова слот A, `attempts=0`, версия 0.52; `MemAvailable` 654 052 kB, PSI 0, `balanced` (`max=1008000`, `governor=performance`), `modd` поднят |
| Питание после загрузки | `balanced` применён: `max=1008000`, `min=408000`, `cur=1008000`, `governor=performance`; GPU `simple_ondemand`, 200 из 650 МГц; `thermal/status` = `applied` |
| Два одновременных запуска | Первый → 0 и строка `launch`, второй → 7 с `another game session is still running` |
| Возврат питания после сеанса | Заглушка поднимала до 1 296 000 и GPU в `performance`; вернулись 1 008 000 и `simple_ondemand`, замок и снимок удалены |
| Запись запуска на 0.52 | `session=463-…`, `system=md`, `runtime=native`, `exit=0`, `signal=0`, `save=unavailable` |
| Свободное место `/data` после уборки | 287 644 kB (89 % занято до уборки образа и тестовых файлов) |

## 2026-11-21 · 0.52, откат на карте и реальные коды ввода

| Проверка | Результат |
| --- | --- |
| Откат A→B | `switch B` (generation 6) → `reboot -f` → `root=PARTLABEL=DEEPOS_B`, версия `0.51-v20-test`, `--selftest` = `status=ok`, `input=r36s_Gamepad` |
| Возврат B→A | `switch A` (generation 7) → `reboot -f` → `root=PARTLABEL=DEEPOS_A`, версия `0.52-v20-test`, `attempts=0`, `rollback=false` |
| Питание после цикла | На B остался `max` от прежних опытов; на A возвращён `--set-power balanced` → `applied`, `max=1008000`, `min=408000`, `cur=1008000`, `governor=performance`, GPU `simple_ondemand` |
| Зависший потомок | Потомок с `trap '' TERM` добит группой через 1,5 с; лаунчер вернул 0, процесс исчез, время < 5 с (`launch_test`) |
| Наборы `tests/run-all.sh` | 24 набора PASS, 0 FAIL |
| Узлы ввода | `pwrkey` (event0), `adc-keys` (event1, только громкость), `Headphones` (event2), `r36s_Gamepad` (js0/event3) |
| Коды кнопок геймпада | `0x130–0x13f` (A/B/X/Y, L1/R1/L2/R2, Select, Start, Mode, L3/R3) и `BTN_DPAD_* 0x220–0x223` |
| Код Fn на V20 | Узел `/joypad/sw13` (`GPIO BTN_FN`) объявляет `linux,code = 0x13c` = `BTN_MODE`; `KEY_FN` (0x1d0) отсутствует в битовых картах всех устройств |
| Расхождение DTB и репозитория | Наш DTS: Menu=`BTN_MODE`, Fn=`KEY_FN`; прошитый вендорский DTB: Fn=`BTN_MODE`, отдельного `KEY_FN` нет |
| Fn в игровом режиме | Лаунчер получает `DP_KEY_FN`, но `game_only` фильтр его отбрасывает; прямого биндинга Fn в RetroArch нет (в строке `r36s_Gamepad` для SDL отсутствует `guide`) |
