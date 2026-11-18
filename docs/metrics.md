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

