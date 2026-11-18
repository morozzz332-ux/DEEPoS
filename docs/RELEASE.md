# DEEPoS release

- image sha256: `0158ac69c0e71c504d989b915eedd69c454c0283a6dab5a41ff55acf0d18d195`
- image size: 4294967296 bytes
- BOOT version: `0.23-dev`
- git: `main` at `9dfcea5`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46836 | `430540c59e7d1b1255faf6c58b929c97a2b6ddd271dbf4ef2f8345ed70044688` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75461654 | `dir` | `build/boot` |
| rootfs | 2355200 | `738d2f0699788ec06d4eef3e64b7063f7c5152a28406f9e6841fc15e6a5addc4` | `build/rootfs.squashfs` |
| image | 4294967296 | `0158ac69c0e71c504d989b915eedd69c454c0283a6dab5a41ff55acf0d18d195` | `build/deepos-r36s-v20.img` |
| idbloader | 113194 | `da92d9bb07fb8a635a661ddac22f965a35fdd8c118ce9823e22145eb391a42f0` | `build/uboot/idbloader.img` |
| u-boot | 1304064 | `60bbe765838fddabc48a85dbc59bcd3cac42e186f1da20f5e090a1d02e8dfd8e` | `build/uboot/u-boot.itb` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root .
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
python3 tools/dpflash.py --list          # номер карты, не гадать
python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\.\PhysicalDriveN --expect-sha256 <sha выше>
```
