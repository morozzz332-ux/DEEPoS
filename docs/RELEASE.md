# DEEPoS release

- image sha256: `4a647723d8d493a879ef28e0e7d46b39f76864fd26d43dcb675aae07649029cf`
- image size: 4294967296 bytes
- BOOT version: `0.20-dev`
- git: `main` at `d841377`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46836 | `430540c59e7d1b1255faf6c58b929c97a2b6ddd271dbf4ef2f8345ed70044688` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75461654 | `dir` | `build/boot` |
| rootfs | 2355200 | `ebfc3faccf8fdc134c6bd216a1ee39fe2d6c2133e2ecac209602310e262d68f9` | `build/rootfs.squashfs` |
| image | 4294967296 | `4a647723d8d493a879ef28e0e7d46b39f76864fd26d43dcb675aae07649029cf` | `build/deepos-r36s-v20.img` |
| idbloader | 113194 | `da92d9bb07fb8a635a661ddac22f965a35fdd8c118ce9823e22145eb391a42f0` | `build/uboot/idbloader.img` |
| u-boot | 1304064 | `60bbe765838fddabc48a85dbc59bcd3cac42e186f1da20f5e090a1d02e8dfd8e` | `build/uboot/u-boot.itb` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root .
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
python3 tools/dpflash.py --list          # номер карты, не гадать
python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\.\PhysicalDriveN --expect-sha256 <sha выше>
```
