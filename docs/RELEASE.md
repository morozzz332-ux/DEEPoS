# DEEPoS release

- image sha256: `c824889e9138e7f9aa1ec9e76aa9e17ea598250c86bcd35fe90ae2e16f65f6cd`
- image size: 4294967296 bytes
- BOOT version: `0.19-dev`
- git: `main` at `3ae94fb`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46564 | `d433e75a4d59fbbcc1d21585ed23009467fcc1218330de695bbdb89f863aeb0a` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75461382 | `dir` | `build/boot` |
| rootfs | 2355200 | `ebfc3faccf8fdc134c6bd216a1ee39fe2d6c2133e2ecac209602310e262d68f9` | `build/rootfs.squashfs` |
| image | 4294967296 | `c824889e9138e7f9aa1ec9e76aa9e17ea598250c86bcd35fe90ae2e16f65f6cd` | `build/deepos-r36s-v20.img` |
| idbloader | 113194 | `da92d9bb07fb8a635a661ddac22f965a35fdd8c118ce9823e22145eb391a42f0` | `build/uboot/idbloader.img` |
| u-boot | 1304064 | `60bbe765838fddabc48a85dbc59bcd3cac42e186f1da20f5e090a1d02e8dfd8e` | `build/uboot/u-boot.itb` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root .
python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img
python3 tools/dpflash.py --list          # номер карты, не гадать
python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\.\PhysicalDriveN --expect-sha256 <sha выше>
```
