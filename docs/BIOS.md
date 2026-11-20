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
`/flash/report/bios.txt` при каждой загрузке. У каждой строки есть четвёртая
колонка: `required`, `hle` или `optional`.

```
bios_ready=2/12
bios_missing=9
bios_optional=1
bios_dir=/storage/bios
3do=missing(panafz1.bin)
amiga=missing(kick34005.A500)
...
atari_st=/storage/bios/tos.img
```

`bios_missing` считает только те системы, без дампа которых игра не пойдёт;
`bios_optional` — те, где ядро умеет обходиться без файла.

Проверить вручную: `/usr/local/bin/bios-check.sh`.

### Какие системы запускаются без дампа

| Система | Ядро | Что будет без BIOS |
|---|---|---|
| PlayStation | `pcsx_rearmed` | игра стартует через HLE; не работают карты памяти и часть CD-функций |
| Game Boy Advance | `mgba` | всё работает, дамп нужен только для точных замеров и «спящего» режима |
| Dreamcast | `flycast` | частичный HLE-загрузчик; часть игр требует настоящий `dc_boot.bin` |

Остальные девять систем из таблицы без своего дампа не запускаются: Saturn,
Sega CD, PC Engine CD, Nintendo DS, NeoGeo, 3DO, Amiga, Sharp X68000, C64.

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
