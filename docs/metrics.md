# Метрики DEEPoS

Заполняется после каждого сданного этапа. Пустое значение = не измерено (не «норма»).

| Дата | Этап | idle ОЗУ, МБ | MemAvailable, МБ | Загрузка до кадра, с | Демонов | SoC °C (4 потока) | FPS PSP-3D | Тесты |
|---|---|---|---|---|---|---|---|---|
| 2026-11-18 | baseline (Arch-R) | 263–318 | 414–468 | 20–30 | 7+ | 79.6 (1416 МГц) | 20–30 | — |
| 2026-11-18 | P0 launcher (host) | — | — | — | — | — | — | 7 экранов: PASS (1.0 с) |
| 2026-11-18 | P4b modd (host) | — | — | — | — | — | — | modd: PASS (0.64 с) |
| 2026-11-18 | P4c saved (host) | — | — | — | — | — | — | saved: PASS (0.15 с) |

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
