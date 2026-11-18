# DEEPoS release

- image sha256: `b5de8980dc9df69a180480cdbadc4ba37a96717a8e2cc0500539e0883b6e5cc5`
- image size: 4294967296 bytes
- BOOT version: `0.26-dev`
- git: `?` at `?`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 74490368 | `f91b62257a28c2369431e8e51c4058f7bffad6c7b267835dfac4b3829bd97729` | `build/kernel/Image` |
| dtb | 46836 | `430540c59e7d1b1255faf6c58b929c97a2b6ddd271dbf4ef2f8345ed70044688` | `build/kernel/rk3326-r36s-v20.dtb` |
| boot | 75461975 | `dir` | `build/boot-0.26-dev` |
| rootfs | 2392064 | `7470bd6e6f66eb231c8ad6edd73e71ae4f16efe32be6e6463d1e43c05209a971` | `build/rootfs-final.squashfs` |
| image | 4294967296 | `b5de8980dc9df69a180480cdbadc4ba37a96717a8e2cc0500539e0883b6e5cc5` | `build/deepos-r36s-v20-0.26-dev.img` |
| Rockchip donor chain | 16744448 | `b80637ba27a996fec3ceff64a850af2a968f095ae1be0e1483b46551f67cdec0` | `<archr-clone-image>` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root . --boot build/boot-0.26-dev --rootfs build/rootfs-final.squashfs --image build/deepos-r36s-v20-0.26-dev.img --loader-donor <archr-clone-image>
python3 tools/verify-image.py --loader-donor <archr-clone-image> build/deepos-r36s-v20-0.26-dev.img
python3 tools/dpflash.py --list          # номер карты, не гадать
```

Из PowerShell с правами администратора, подставив номер карты и её образ:

```powershell
.\flash-deepos.ps1 -Image build/deepos-r36s-v20-0.26-dev.img -Sha256 b5de8980dc9df69a180480cdbadc4ba37a96717a8e2cc0500539e0883b6e5cc5
```
