# BIOS и прошивки эмуляторов

Эмуляторы работают без «магических» настроек, но части систем нужны дампы
прошивок (BIOS). DEEPoS **не распространяет** такие файлы: положить их можно
только самому, из своей консоли или из легально купленной игры. Всё, что
распространяется свободно, уже лежит в образе.

## Что уже установлено

| Система | Файл в `/storage/bios` | Лицензия |
|---|---|---|
| Atari ST / TT / Falcon | `tos.img` (EmuTOS 1.3) | GPL, поставляется |
| MSX / MSX2 / MSX2+ | `Machines/MSX*` (C-BIOS) | BSD-подобная, поставляется |

Эти файлы появляются автоматически при первом включении: их кладёт
`tools/install-open-bios.py` из каталога `bios/` репозитория, сверяя sha256 из
`bios/manifest.tsv`. Установщик никогда не перезаписывает чужие файлы.

## Что нужно положить самому

Полный список — `board/r36s-v20/data/bios-required.tsv`; на устройстве он
лежит как `/usr/share/deepos/bios-required.tsv`, а отчёт о наличии пишется в
`/flash/report/bios.txt` при каждой загрузке:

```
bios_ready=2/27
bios_dir=/storage/bios
amiga=missing(kick34005.A500)
dreamcast=missing(dc_boot.bin)
gba=missing(gba_bios.bin)
neogeo=missing(neogeo.zip)
...
psx=/storage/bios/scph5501.bin
```

Проверить вручную: `/usr/local/bin/bios-check.sh`.

Самые частые случаи:

| Система | Файлы | Замечание |
|---|---|---|
| PlayStation | `scph5501.bin` (US), `scph5502.bin` (EU), `scph5500.bin` (JP) | нужен любой один |
| Dreamcast | `dc_boot.bin`, `dc_flash.bin` | `dc_flash.bin` необязателен |
| Saturn | `sega_101.bin` (JP), `mpr-17933.bin` (US/EU) | Flycast/Yabause |
| Sega CD | `bios_CD_U.bin`, `bios_CD_E.bin`, `bios_CD_J.bin` | по региону игры |
| PC Engine CD | `syscard3.pce` | Super CD-ROM2 System Card 3.0 |
| NeoGeo | `neogeo.zip` | обязательна для FBNeo |
| Nintendo DS | `bios7.bin`, `bios9.bin`, `firmware.bin` | melonDS |
| 3DO | `panafz1.bin` | Panasonic FZ-1 |
| Amiga | `kick34005.A500` | Kickstart 1.3 |
| Sharp X68000 | `iplrom.dat`, `cgrom.dat` | px68k |
| Commodore 64 | `kernal-901227-03.bin` | VICE |

## Куда класть

RetroArch ищет прошивки в `system_directory`:

1. карта DEEPoS — `/storage/bios` (виден с ПК как раздел `ROMS`, папка `bios`);
2. вторая карта в слоте TF2 — `/games/bios`.

`retroarch-game.sh` подставляет каталог автоматически: для ROM на второй карте
берётся `/games/bios`, для ROM на основной — `/storage/bios`.

Вложенные каталоги сохраняйте как в таблице (`Machines/MSX/…`), некоторые ядра
ожидают подпапку с именем системы.

## Как это проверить

1. Положить файлы на карту (ПК → раздел `ROMS` → `bios`).
2. На консоли: Настройки → «Сведения» → «Версия» показывает текущую сборку, а
   отчёт лежит в `/flash/report/bios.txt` (`bios_ready=N/M`).
3. Запустить игру системы, для которой положили BIOS: без файла ядро
   показывает чёрный экран или сообщение о отсутствующей прошивке, с файлом —
   запускается.

Отсутствующий BIOS никогда не блокирует запуск остальных систем: каждая строка
отчёта независима.
