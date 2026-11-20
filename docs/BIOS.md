# BIOS и системные файлы

DEEPoS ищет BIOS на карте **TF1** в `ROMS/bios/`. Для игры с TF2
прошивка использует папку `bios/` на TF2, если в ней уже есть файлы. На
карте с раскладкой Arch‑R поддерживается и `roms/bios/`. Если на TF2
нет BIOS, RetroArch использует папку на TF1.

## Свободный комплект

Скопируйте **содержимое** [bios/files/](../bios/files/) в папку `bios`
раздела ROMS. При совпадении имён пропустите замену своих файлов. Скрипт
записывает только отсутствующие файлы и проверяет комплект по SHA‑256.
[Команда установки и лицензии](../bios/README.md)

- **Atari ST, Hatari.** EmuTOS устанавливается как `tos.img`. В параметрах
  ядра выберите образ из системной папки. Некоторые игры требуют свою версию
  Atari TOS. [Документация Hatari](https://docs.libretro.com/library/hatari/)
- **MSX, MSX2 и MSX2+, blueMSX.** C‑BIOS позволяет использовать картриджи.
  Дискеты, кассеты и BASIC требуют отдельной совместимой конфигурации машины.
  [C‑BIOS](https://cbios.sourceforge.net/) · [blueMSX](https://docs.libretro.com/library/bluemsx/)

## У каких игр есть дополнительные требования

| Система и ядро | Что нужно |
| --- | --- |
| Game Boy Advance, mGBA | `gba_bios.bin` необязателен. [mGBA](https://docs.libretro.com/library/mgba/#bios) |
| PlayStation, PCSX ReARMed | Есть встроенная замена. Для отдельных игр подойдёт дамп нужного региона `scph5500.bin`, `scph5501.bin` или `scph5502.bin`. [PCSX ReARMed](https://docs.libretro.com/library/pcsx_rearmed/#bios) |
| Sega CD / Mega CD, Genesis Plus GX | `bios_CD_U.bin`, `bios_CD_E.bin` или `bios_CD_J.bin` по региону игры. [Genesis Plus GX](https://docs.libretro.com/library/genesis_plus_gx/#bios) |
| Dreamcast, Flycast | BIOS хранится в `dc/`. NAOMI и Atomiswave используют системные архивы, соответствующие набору ROM. [Flycast](https://docs.libretro.com/library/flycast/#bios) |
| Neo Geo, FinalBurn Neo | `neogeo.zip` соответствующей версии набора ROM. [FinalBurn Neo](https://docs.libretro.com/library/fbneo/#bios) |
| 3DO, Opera | BIOS нужной модели, например `panafz10.bin`. [Opera](https://docs.libretro.com/library/opera/#bios) |
| ColecoVision, Gearcoleco | `colecovision.rom`. [Gearcoleco](https://docs.libretro.com/library/gearcoleco/#bios) |

Для других систем сначала посмотрите название выбранного ядра. На консоли
его можно увидеть по **X** в списке систем или игр. Затем найдите его в
[таблице путей BIOS](BIOS-CORE-LIST.tsv). Имена считаются относительно
папки `bios/`, включая вложенные каталоги. Для файлов производителя
используйте дампы со своего оборудования.

Таблица охватывает 118 ядер сборки 0.41 bundle r2. Записи о внешних файлах
есть у 65 ядер. Пометки `required` и `optional` перенесены из метаданных
Libretro. Учитывайте регион, модель устройства и выбранный режим. В частности,
запись blueMSX про системные файлы относится к полной раскладке blueMSX.
[Снимок метаданных Libretro](https://github.com/libretro/libretro-core-info/tree/eac3a2784d428444aa2bd472039b5c5540141af1)
