# DEEPoS release

- image sha256: `05598792dd1dd795fa332f467884903721f0c4ffd3d979659675d676ed70a2fe`
- image size: 4294967296 bytes
- BOOT version: `0.17-dev`
- git: `main` at `6279ddd`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46564 | `d433e75a4d59fbbcc1d21585ed23009467fcc1218330de695bbdb89f863aeb0a` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75461382 | `dir` | `build/boot` |
| rootfs | 2117632 | `6c82917b43c406972761096d51778c85748843feba3f010a8205a9fe8ac420cd` | `build/rootfs.squashfs` |
| image | 4294967296 | `05598792dd1dd795fa332f467884903721f0c4ffd3d979659675d676ed70a2fe` | `build/deepos-r36s-v20.img` |
| idbloader | 113194 | `da92d9bb07fb8a635a661ddac22f965a35fdd8c118ce9823e22145eb391a42f0` | `build/uboot/idbloader.img` |
| u-boot | 1304064 | `60bbe765838fddabc48a85dbc59bcd3cac42e186f1da20f5e090a1d02e8dfd8e` | `build/uboot/u-boot.itb` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root .
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
python3 tools/dpflash.py --list          # номер карты, не гадать
python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\.\PhysicalDriveN --expect-sha256 <sha выше>
```
