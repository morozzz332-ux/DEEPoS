# Образы DEEPoS для R36S‑V20

## 0.41-v20-bundle-r2 от 2026-11-20

- image sha256: `c6e262df7b481e13873664d35cb010cc19f3f18fbd75b4df469af17a2774f28f`
- Размер распакованного образа 31 103 909 888 байт.

118 доступных ARM64-ядер и PortMaster. Старый Flycast 2021 заменяется при
запуске современным Flycast. EmuSCV использует проверенную сборку Libretro
Buildbot. Все ядра из доступного списка загрузились и предоставили точку
входа libretro в ARM64-проверке.

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 31103909888 | c6e262df7b481e13873664d35cb010cc19f3f18fbd75b4df469af17a2774f28f | `build/deepos-r36s-v20-0.41-bundle-r2.img.gz` |
| архив | 712342061 | cc07dd9172d43a96457d1df458e7e2b54b30b3054c58562a3b1a82557e0ecc97 | `build/deepos-r36s-v20-0.41-bundle-r2.img.gz` |
| rootfs | 130551808 | 4f7a0ed589206a56e01c204e5924a23c79d86210e537912cf286300d11cec6d9 | `build/deepos-rootfs-0.41-v20-bundle-r2.squashfs` |

Полный образ прошёл 43 проверки структуры. Запись в системный слот
проверена обратным чтением. Проверка экрана
PortMaster, команд геймпада и игр с TF2 выполняется на консоли.

## 0.41-v20-bundle от 2026-11-20

Расширенная сборка с опциональным PortMaster и 119 ядрами RetroArch AArch64.
43 дополнительных ядра размещены в системном squashfs. Выбор ядра доступен
по X, правила размещения портов описаны в [руководстве PortMaster](PORTMASTER.md).

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| rootfs | 130015232 | 571fd17047b4f2167584ffed7b41b43ae79d5e1dd185505431a913d0c4016b5b | `build/deepos-rootfs-0.41-v20-bundle.squashfs` |

Пройдены 22 набора хост-тестов. Все 43 дополнительных ядра загрузились в
проверочном окружении ARM64. Проверены запуск командного интерфейса
PortMaster и наличие драйвера SDL KMSDRM. Экран менеджера, контроллер,
звук и запуск конкретных игр проверяются на консоли.

## 0.41-v20-test от 2026-11-20

- image sha256: `1be6c97e9fa4a8b556d11cf0a0d8c5d864c99f6adfd690b3dca852d268986b53`
- Размер распакованного образа 31 103 909 888 байт. Для карт меньшего размера
  соберите образ с меньшим `SIZE_MIB`.

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 31103909888 | 1be6c97e9fa4a8b556d11cf0a0d8c5d864c99f6adfd690b3dca852d268986b53 | `build/deepos-r36s-v20-0.41-test.img.gz` |
| архив | 333821094 | b28d07c16ad5220fd7b531e04e6b0a9b02b9104c4f07bd06737458f005a9783d | `build/deepos-r36s-v20-0.41-test.img.gz` |
| rootfs | 2592768 | 78f309dc2b17537b44d416c6936dde422660f5556fbf656946aa018c97be5a26 | `build/deepos-rootfs-0.41-v20-test.squashfs` |

Добавлены дата и регион, переключатели модулей, описание по Y, установка
самописных модулей и библиотека TF2. Образ прошёл 43 проверки структуры.
Обратное чтение системного слота на тестовой microSD совпало со сборкой.
Работу TF2 на физической консоли проверяют отдельно.
[Установка](INSTALL.md) · [Метрики](metrics.md)

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
