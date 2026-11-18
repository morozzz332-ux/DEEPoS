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
