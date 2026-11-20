# Статус прототипа DEEPoS (host-уровень)

Обновление 2026-11-20, ветка V20. Тестовая 0.39 содержит обновлённый экран
мониторинга, настройки подсветки/ALSA/лимита CPU и новый путь запуска
RetroArch. Загрузка 0.37 на устройстве зафиксирована в [журнале](journal.md).
Для 0.39 аппаратная приёмка идёт по [DEVICE-TEST-PLAN.md](DEVICE-TEST-PLAN.md).
Архив из локального донора содержит RetroArch 1.22.2, 76 ядер AArch64 и
команды для 112 систем из 124 записей донора. Эти числа относятся к собранному
комплекту. Проверка игр на консоли ведётся по каждой системе.

Исторический снимок на 2026-11-18 (раунд 21). Здесь только то, что проверено автоматически без
консоли, и то, что ждёт реального железа. Числа — из `docs/metrics.md`.

Образ для записи: `build/deepos-r36s-v20.img`, 4 294 967 296 B,
sha256 `349a900d6b318888851e35a2260893db2b7eadfb4ec99e08b194935e0d4bf2c3`,
BOOT-дерево `0.13-dev`. Перед записью: `python3 tools/preflight.py --root .` → `PREFLIGHT: GO (32 checks)`.

## Работает и покрыто тестами (15 наборов)

| Слой | Что именно | Чем проверено |
|---|---|---|
| Загрузчик | вендорский `idbloader.img` + `u-boot.itb` (RK3326), раскладка 32 KiB / 8 MiB, BOOT с `start_mib: 16` | `tests/image_test.py` (loader placement) |
| Ядро/DTB | кросс-сборка 6.12.56: `Image` 74 490 368 B, DTB 46 564 B, `linux.config` 115 символов | `tests/board_test.py`, `tools/kconfig-check.sh` |
| BOOT | `KERNEL`, `dtbs/`, `extlinux.conf` (`LABEL DEEPoS`, `root=LABEL=DEEPOS_A|B`), `logo.bmp`, `MANIFEST.json` с sha256 | `tests/boot_test.py` |
| Rootfs | static busybox + `launcher`/`modd`/`saved`/`updatr`, overlay `inittab`/`rcS`, `os-release` | `tests/board_test.py`, `tests/image_test.py` (DATA через `debugfs`) |
| Образ карты | GPT: BOOT / DEEPOS_A / DEEPOS_B / DATA / ROMS, побайтовая прошивка, backup GPT | `tests/image_test.py`, `tools/verify-image.py` (39 checks) |
| Готовность | preflight: ядро, `compatible` DTB, имя FDT = файл в `BOOT/dtbs`, sha256 KERNEL, бинари и `x` на `rcS`, загрузчики, verify-image | `tests/preflight_test.py` |
| UI | 7 экранов, шрифты 12×12/10×10, детерминизм, пустая библиотека, склонения | `tests/run.py` + golden |
| Ввод | evdev (без `linux/input.h`), навигация вкладок/списков, синтетические `--keys` | `tests/input_test.py` |
| Вывод | fbdev RGB565 (плюс 24/32 bpp), блит побайтово = PPM | `tests/display_test.py` |
| Настройки | `/data/config/settings.toml` → `brightness`/`volume`/`profile`, sysfs backlight, `cpu-profile`; карточки «Дисплей/Звук/Питание» читают значения | `tests/config_test.py`, `tests/selftest_test.py` |
| Модули | `modd` (NDJSON, таймауты, watchdog 3/10 мин), протокол thermal/saves, действия из UI | `tests/modd_test.py`, `tests/modules_test.py`, `tests/launcher_mod_test.py` |
| Сейвы | атомарное хранилище `saved` (tmp→fsync→rename→fsync(dir)), журнал, recover | `tests/saved_test.py` |
| A/B | `updatr` begin/good/switch, откат на 4-й попытке, синхронизация `root=LABEL=` в extlinux | `tests/updatr_test.py` |
| Загрузка системы | `rcS` монтирует BOOT→`/flash`, DATA→`/data`, ROMS→`/storage`; A/B до `exit 0`; UI из `inittab ::respawn`; readiness-строка | `tests/board_test.py` (mounts, order, handover, robustness) |
| Запуск игры | `emulators.toml`, `%ROM%`/`%SLOT%`, hook allow/deny, «Продолжить», обновление `continue.tsv` | `tests/launch_test.py` |
| Отладка | `getty` на `ttyS2` (1500000), `passwd`/`group` с root без пароля | `tests/board_test.py` (handover) |
| Диагностика | `launcher --selftest` (ROM/continue/emulators/modd/fb/input/`data_ok`/`roms_ok`) | `tests/selftest_test.py` |

Сборка без `make` на Windows: всё гоняется через docker-образы `deepos-build:local`
и `deepos-cross:local` (`make docker-test` / `sh tests/run-all.sh`).

## Не проверено (этап 2 — реальная консоль)

| Риск | Как проверить |
|---|---|
| Загрузчик + DTB на живой V20 (панель, кнопки, звук) | первый буст по `docs/DEVICE-TEST-PLAN.md`: экран, `--selftest`, «Проверка контроллера» |
| fbdev на реальном `/dev/fb0` (stride, 16 bpp) | после буста: `--screen continue --fb /dev/fb0`, глазами |
| evdev-имена (`gpio-keys`, `adc-joystick`) | `--selftest` → `input_events>0`, нажатия в UI |
| Монтирования и `updatr` на живой карте | `cat /proc/mounts`, `updatr --state /data --boot /flash status` |
| Бюджет ОЗУ (цель ≤150 МБ idle) | `free`, `ps` после буста; сравнить с Arch-R (263–318 МБ) |
| Температуры под нагрузкой | стресс 4 потока 45 с при 1416 МГц, порог троттлинга 85 °C |
| Время загрузки (цель ≤12 с) | секундомер от нажатия до первого кадра |
| Порты и эмуляторы на железе | запуск 2–3 портов и PS1/PSP-игры |

## Известные ограничения, принятые сознательно

- 1512 МГц недоступны в Arch-R-ядре (нет `cpufreq/boost`); свой DTB тоже не спешит:
  максимум 1416 МГц, дальше — только охлаждение.
- Wi-Fi нет: сеть только через USB-NCM (или MTP), плюс Samba/HTTP поверх.
- 2 ГБ ОЗУ — только BGA-пайка; программно максимум zram 1.5–2 ГБ.
- `make` на Windows-хосте нет — цели Makefile выполняются эквивалентными docker-командами.
