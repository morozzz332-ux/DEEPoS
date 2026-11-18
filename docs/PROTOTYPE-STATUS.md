# Статус прототипа DEEPoS (host-уровень)

Снимок на 2026-11-18. Что уже проверено автоматически, а что ждёт реальной консоли.

## Работает и покрыто тестами

| Слой | Что именно | Чем проверено |
|---|---|---|
| Загрузчик | вендорский `idbloader.img` + `u-boot.itb` (RK3326), раскладка 32 KiB / 8 MiB | `tests/image_test.py` (loader placement) |
| Ядро/DTB | кросс-сборка 6.12.56, DTB 46 564 B, `linux.config` 115 символов | `tests/board_test.py`, `tools/kconfig-check.sh` |
| BOOT | `KERNEL`, `dtbs/`, `extlinux.conf`, `logo.bmp`, `MANIFEST.json` | `tests/boot_test.py` |
| Rootfs | static busybox + launcher/modd/saved/updatr, overlay `inittab`/`rcS` | `tests/board_test.py`, `tests/image_test.py` (DATA/debugfs) |
| Образ карты | GPT: BOOT / DEEPOS_A / DEEPOS_B / DATA / ROMS, побайтовая прошивка | `tests/image_test.py` |
| UI | 7 экранов, 12×12/10×10 шрифты, детерминизм рендера | `tests/run.py` + golden |
| Ввод | evdev, навигация вкладок/списков, синтетические `--keys` | `tests/input_test.py` |
| Вывод | fbdev RGB565 (плюс 24/32 bpp), блит = PPM | `tests/display_test.py` |
| Модули | `modd` (NDJSON, таймауты, watchdog), thermal/saves протокол, действия из UI | `tests/modd_test.py`, `tests/modules_test.py`, `tests/launcher_mod_test.py` |
| Сейвы | атомарное хранилище `saved`, журнал, recover | `tests/saved_test.py` |
| A/B | `updatr` (begin/good/switch, rollback на 4-й попытке) | `tests/updatr_test.py` |
| Запуск игры | `emulators.toml`, `%ROM%`/`%SLOT%`, hook allow/deny, «Продолжить» | `tests/launch_test.py` |
| Диагностика | `launcher --selftest` (ROM/continue/emulators/modd/fb/input) | `tests/selftest_test.py` |

## Не проверено (этап 2 — реальная консоль)

| Слой | Риск | Как проверять |
|---|---|---|
| Панель ST7703 + DSI-тайминг | нет картинки или «снег» | первый буст, `dmesg | grep -i dsi` |
| gpio-keys / adc-joystick | кнопки не те, стики уехали | `--selftest`, «Проверка контроллера» |
| fbdev emulation | нет `/dev/fb0` | `fb_present=1` в selftest |
| Аудио (rk817_codec) | нет звука | `aplay`, наушники/динамик |
| Зарядка/батарея (rk817) | проценты врут | `/sys/class/power_supply/*` |
| Память в простое | >150 МБ | `--selftest` + `/proc/meminfo`, `docs/metrics.md` |
| Реальная загрузка | >12 с, чёрный экран | секундомер + `dmesg` |
| Переключение A/B на устройстве | не грузится второй слот | `updatr switch B` + ребут |

## Бэкап перед прошивкой

Обязательно снять образ текущей карты (см. `docs/DEVICE-TEST-PLAN.md` §1) — DEEPoS
пишет в первые 4 ГиБ, включая загрузочную цепочку.
