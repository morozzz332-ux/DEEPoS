# R36S-V20 board support

Плата: клон `R36S-V20 2025-05-18`, SoC RK3326, 1 ГБ LPDDR3, PMIC RK817,
панель ST7703 (MIPI-DSI), два гнезда USB-C (OTG — данные, CHARGE — питание).

## Разметка карты (`layout.json`)

| Раздел | ФС | Размер | Метка | Назначение |
|--------|----|--------|-------|------------|
| BOOT | FAT32 | 256 MiB | BOOT | `KERNEL`, `dtbs/`, `overlays/`, `extlinux/`, `logo.bmp` |
| SYS_A | squashfs (zstd) | 700 MiB | DEEPOS_A | корневая ФС, слот A |
| SYS_B | squashfs (zstd) | 700 MiB | DEEPOS_B | корневая ФС, слот B (A/B-обновления) |
| DATA | ext4 | 1536 MiB | DATA | конфиги, сейвы, модули, swap-файл |
| ROMS | exFAT | остаток | ROMS | ROM'ы, виден с ПК |

Таблица — GPT (protective MBR + primary/backup заголовки). Разделы выровнены
по 1 MiB: так дешевле чтение на eMMC/SD-контроллере и совпадает с тем, что
делает `parted` на реальной карте.

## Почему GPT, а не MBR

В MBR всего 4 первичных раздела, а нам нужно пять. Extended-цепочка EBR на
этом классе устройств — лишние грабли (U-Boot, утилиты разметки в chroot),
поэтому используется GPT: и Linux, и Windows читают её без доп. драйверов.

## Порядок записи образа

1. Первые 34 сектора (protective MBR + заголовок GPT + массив записей) **не
   пишутся** до конца: пока таблицы нет, Windows не монтирует разделы.
2. Тело образа пишется с offset 17 KiB.
3. В самом конце пишется таблица (и резервная копия GPT в хвосте образа).

Причина: как только таблица валидна, Mount Manager монтирует FAT/exFAT, и
запись в смонтированный том падает с `win32=5` (ERROR_ACCESS_DENIED на
`\\.\PhysicalDriveN`). Этот же приём (MBR последним) использовался при
прошивке Arch-R — см. `docs/GUIDE.md`.

## Сборка и проверка

```sh
make image        # полный образ (нужен Docker: mkfs.vfat, mksquashfs, mkfs.ext4, mkfs.exfat)
make image-test   # маленький образ 128 MiB + проверка структур и прошивальщика
```

`tools/mkimage.py` строит образ детерминированно: GUID'ы разделов выводятся из
имени образа и имени раздела, поэтому две сборки одинаковых входов дают
побайтово одинаковый файл (на этом держатся golden-тесты).

`tools/dpflash.py` пишет образ на карту или в файл (`--dry-run`, `--target`,
`--expect-sha256`, `--no-defer-table`). На Windows `--target \\.\PhysicalDriveN`
требует прав администратора и закрытого проводника.

## Rockchip boot chain (ниже первого раздела)

| Смещение | Что | Кто пишет |
|---|---|---|
| 32 KiB (сектор 64) | `idbloader.img` (TPL + SPL) | `mkimage.py --loader` |
| 8 MiB (сектор 16384) | `u-boot.itb` (U-Boot proper + BL31) | `mkimage.py --loader` |
| 16 MiB (сектор 32768) | раздел `BOOT` (FAT32) | `mkimage.py --boot` |

Поэтому `BOOT` в `layout.json` объявлен с `"start_mib": 16`: разделы не должны
накрывать загрузчик. Mainline U-Boot не поддерживает RK3326, поэтому загрузчик
собирается из вендорского форка (`tools/build-uboot.sh`).

