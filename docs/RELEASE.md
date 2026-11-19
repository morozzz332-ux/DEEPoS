# DEEPoS 0.33 для R36S‑V20

- image sha256: `457abb9029376cffb1c1cfcea177739e3e29976ab8a0736e966f306922cf979e`
- Размер образа 4 294 967 296 байт
- BOOT version `0.33-v20`

| Артефакт | Байты | SHA-256 | Путь |
|---|---:|---|---|
| image | 4294967296 | 457abb9029376cffb1c1cfcea177739e3e29976ab8a0736e966f306922cf979e | `build/v20-boot-033/deepos-r36s-v20-0.33.img.gz` |
| Ядро Arch-R Linux 6.12.114 | 19449864 | `895f6cb7fef8286a7b177ed733b2ac362b0c7f5f9aeb35fed4f71e685f0fa5ec` | `BOOT/KERNEL` |
| DTB V20 с оверлеем | 72915 | `f7cca1d9c73f8fd70207a20f5784829c929c438a6dabd72bbece20e304ecc41e` | `BOOT/dtbs/rk3326-r36s-v20.dtb` |
| Драйвер геймпада | 40136 | `c915f32218c5bd5466abf466e1e28f13e6cb10c4251c8f663c8f30e0700450ea` | `/lib/modules/6.12.114/archr-singleadc-joypad.ko` |
| Загрузочная область Rockchip | 16744448 | `b80637ba27a996fec3ceff64a850af2a968f095ae1be0e1483b46551f67cdec0` | `<archr-clone-image>` |

Сборка описана в [диагностике V20](V20-BOOT-DIAGNOSIS.md). Перед записью
образ прошёл preflight, проверку GPT, FAT32, обеих системных областей
и совпадения загрузчика с донором. Windows-скрипт читает gzip напрямую.
Размер и SHA-256 относятся к распакованным данным.

```powershell
python tools/dpflash.py --list
.\flash-deepos.ps1 -Disk $sdDiskNumber -Image build/v20-boot-033/deepos-r36s-v20-0.33.img.gz -Sha256 457abb9029376cffb1c1cfcea177739e3e29976ab8a0736e966f306922cf979e -Fresh
```
