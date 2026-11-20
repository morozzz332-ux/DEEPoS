# Образы DEEPoS для R36S‑V20

## 0.40-v20-test от 2026-11-20

- image sha256: `1261b3e2666a4915a643f8ce5f552ed0d07d0c7acbbc1828c3bb7700f0e0449c`
- Размер распакованного образа 4 294 967 296 байт.

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 4294967296 | 1261b3e2666a4915a643f8ce5f552ed0d07d0c7acbbc1828c3bb7700f0e0449c | `build/deepos-r36s-v20-0.40-test.img.gz` |
| rootfs | 2564096 | 8f2c187bdaf849e75021e0e03dde8a73ce416c137a605d3c03f7da75cac13ebd | `build/deepos-rootfs-0.40-v20-test.squashfs` |

Новые настройки RetroArch и режимы OTG описаны в [руководстве](GUIDE.md).
Образ прошёл 43 проверки структуры, загрузчика и файлов BOOT. DHCP, обнаружение
диска ROMS на ПК и запуск игр с новыми настройками проверяются на R36S‑V20.

## 0.39-v20-terminal от 2026-11-20

- image sha256: `52140057a9cbd6c8b9a5cb54db7a6ebfa1d7069a3f6217eee4b87fa167dab19a`
- Размер распакованного образа 4 294 967 296 байт.
- BOOT version `0.39-v20-terminal`.

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 4294967296 | 52140057a9cbd6c8b9a5cb54db7a6ebfa1d7069a3f6217eee4b87fa167dab19a | `build/deepos-r36s-v20-0.39-terminal.img.gz` |
| rootfs | 2560000 | 3c30dbae5d4fa64493207f761a217c15671dd1cbbd015a7fc054e44d9ae13d6c | `build/deepos-rootfs-0.39-v20-terminal.squashfs` |

Изменены палитра, шрифты и логотип, добавлены три коротких системных сигнала.
Загрузка на V20 выводит журнал на UART, логотип рисуется после появления
fbdev, лаунчер выводит первый кадр без ожидания кнопки. В DATA включены 76 ядер
RetroArch и команды 112 систем. Следующий этап — интеграция PortMaster.

Размер и SHA-256 образа относятся к распакованным данным. Для записи используйте
тестовую microSD или сохраните резервную копию текущей карты. После записи
проверьте загрузку и звук по [DEVICE-TEST-PLAN.md](DEVICE-TEST-PLAN.md).

## 0.39-v20-test от 2026-11-20

Проверочная сборка с RetroArch 1.22.2 и 76 ядрами AArch64 в DATA. Реестр
содержит 112 систем из локального каталога Arch‑R Clone. Оба системных слота
содержат один и тот же squashfs 0.39. BOOT использует ядро 6.12.114, DTB панели
и цепочку загрузчика предыдущей сборки V20.

| Артефакт | Байты | SHA-256 |
|---|---:|---|
| `build/deepos-r36s-v20-0.39-test.img` | 11936989184 | `01d9212aaec11b4cb89985559b70708fb4af3766171be8a9d5c407619cbc4c0e` |
| `build/deepos-rootfs-0.39-v20-test.squashfs` | 2560000 | `1a82899ec8e888b8bdc9c6b8909b9778c383680ac69ed8f411178c68813aed77` |

Пройдены 23 набора хост-тестов. Проверены GPT, BOOT, соответствие загрузчика
донору и содержимое обоих системных слотов. Проверку физической консоли вести
по [DEVICE-TEST-PLAN.md](DEVICE-TEST-PLAN.md). Размещение ROM, BIOS и установка
отдельного комплекта описаны в [EMULATORS.md](EMULATORS.md).

Для записи на отдельную тестовую microSD укажите её номер после сверки `Get-Disk`.

```powershell
.\flash-deepos.ps1 -Disk $sdDiskNumber -Image build/deepos-r36s-v20-0.39-test.img -Sha256 01d9212aaec11b4cb89985559b70708fb4af3766171be8a9d5c407619cbc4c0e -Fresh
```

## 0.37-v20

- image sha256: `90cb6940e1dd6ebc34028da747d6bec2bb33c7830de0cbfef541098df29c83c0`
- Размер образа 4 294 967 296 байт
- BOOT version `0.37-v20`

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 4294967296 | 90cb6940e1dd6ebc34028da747d6bec2bb33c7830de0cbfef541098df29c83c0 | `build/v20-boot-037/deepos-r36s-v20-0.37.img.gz` |
| Ядро Arch-R Linux 6.12.114 | 19449864 | `895f6cb7fef8286a7b177ed733b2ac362b0c7f5f9aeb35fed4f71e685f0fa5ec` | `BOOT/KERNEL` |
| DTB V20 с оверлеем | 72915 | `f7cca1d9c73f8fd70207a20f5784829c929c438a6dabd72bbece20e304ecc41e` | `BOOT/dtbs/rk3326-r36s-v20.dtb` |
| Каталог для монтирования корня | 240 | `44e69db9ade9416ed715afbf578aed6fbd835965a4b18c7ef67ef791737399a5` | `BOOT/ROOTDIR.CPIO` |
| Драйвер геймпада | 40136 | `c915f32218c5bd5466abf466e1e28f13e6cb10c4251c8f663c8f30e0700450ea` | `/lib/modules/6.12.114/archr-singleadc-joypad.ko` |
| Загрузочная область Rockchip | 16744448 | `b80637ba27a996fec3ceff64a850af2a968f095ae1be0e1483b46551f67cdec0` | `<archr-clone-image>` |

Сборка описана в [диагностике V20](V20-BOOT-DIAGNOSIS.md). Перед записью
образ прошёл preflight, проверку GPT, FAT32, обеих системных областей
и совпадения загрузчика с донором. Windows-скрипт читает gzip напрямую.
Размер и SHA-256 относятся к распакованным данным.

```powershell
python tools/dpflash.py --list
.\flash-deepos.ps1 -Disk $sdDiskNumber -Image build/v20-boot-037/deepos-r36s-v20-0.37.img.gz -Sha256 90cb6940e1dd6ebc34028da747d6bec2bb33c7830de0cbfef541098df29c83c0 -Fresh
```
