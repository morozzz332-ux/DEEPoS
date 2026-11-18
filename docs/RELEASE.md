# DEEPoS release

- image sha256: `f5f1e3c865b045602db22e8c9effe68f1e544ca29751288941bfb0bda5711896`
- image size: 4294967296 bytes
- BOOT version: `0.16-dev`
- git: `main` at `cbf4ae7`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46564 | `d433e75a4d59fbbcc1d21585ed23009467fcc1218330de695bbdb89f863aeb0a` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75459727 | `dir` | `build/boot` |
| rootfs | 2117632 | `684e7f7f8709531dfde962fd25bbbffe64dbe16e99f09dc81a64eb3a43946e4e` | `build/rootfs.squashfs` |
| image | 4294967296 | `f5f1e3c865b045602db22e8c9effe68f1e544ca29751288941bfb0bda5711896` | `build/deepos-r36s-v20.img` |
| idbloader | 113194 | `da92d9bb07fb8a635a661ddac22f965a35fdd8c118ce9823e22145eb391a42f0` | `build/uboot/idbloader.img` |
| u-boot | 1304064 | `60bbe765838fddabc48a85dbc59bcd3cac42e186f1da20f5e090a1d02e8dfd8e` | `build/uboot/u-boot.itb` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root .
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
python3 tools/dpflash.py --list          # номер карты, не гадать
python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\.\PhysicalDriveN --expect-sha256 <sha выше>
```
