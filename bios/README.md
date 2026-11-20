# Свободные BIOS для DEEPoS

Содержимое [files/](files/) соответствует папке `bios/` на разделе ROMS.
Например, `files/tos.img` нужно разместить как `ROMS/bios/tos.img`.

| Система | Что входит | Источник |
| --- | --- | --- |
| Atari ST | EmuTOS 1.4, образ 192 КиБ UK для Hatari | [Релиз EmuTOS 1.4](https://sourceforge.net/projects/emutos/files/emutos/1.4/) |
| MSX, MSX2, MSX2+ | C‑BIOS 0.29a и конфигурации blueMSX для картриджей | [Релиз C‑BIOS 0.29a](https://sourceforge.net/projects/cbios/files/cbios/0.29/) |

Пути в конфигурациях C‑BIOS приведены к именам машин, используемым в
DEEPoS. Архив с исходным кодом EmuTOS и лицензии компонентов входят
в комплект. [Исходники EmuTOS](source/emutos-src-1.4.tar.gz) ·
[Лицензии](licenses/) · [SHA‑256](manifest.tsv)

Чтобы проверить и скопировать файлы без перезаписи существующих BIOS:

```powershell
python tools/install-open-bios.py --roms R:/
```

Укажите букву своего раздела ROMS. Команде нужен Python 3.11 или новее.
[Установка вручную и список BIOS](../docs/BIOS.md)
