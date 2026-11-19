# DEEPoS release

- image sha256: `2671df94319b334ed65db990342bbae80cb10e11d2210a7e062cd907f8f3ae29`
- image size: 4294967296 bytes
- BOOT version: `0.27-v20-test`
- git: `?` at `?`

| artefact | bytes | sha256 | path |
|---|---|---|---|
| kernel | 19449864 | `895f6cb7fef8286a7b177ed733b2ac362b0c7f5f9aeb35fed4f71e685f0fa5ec` | `build/v20-hw-kernel/Image` |
| dtb | 72915 | `f7cca1d9c73f8fd70207a20f5784829c929c438a6dabd72bbece20e304ecc41e` | `build/v20-hw-kernel/rk3326-r36s-v20.dtb` |
| boot | 20447636 | `dir` | `build/boot-0.27-v20` |
| rootfs | 2392064 | `7470bd6e6f66eb231c8ad6edd73e71ae4f16efe32be6e6463d1e43c05209a971` | `build/rootfs-final.squashfs` |
| image | 4294967296 | `2671df94319b334ed65db990342bbae80cb10e11d2210a7e062cd907f8f3ae29` | `build/deepos-r36s-v20-0.27-test.img` |
| Rockchip donor chain | 16744448 | `b80637ba27a996fec3ceff64a850af2a968f095ae1be0e1483b46551f67cdec0` | `<archr-clone-image>` |

Проверки перед записью:

```sh
python3 tools/preflight.py --root . --kernel build/v20-hw-kernel/Image --dtb build/v20-hw-kernel/rk3326-r36s-v20.dtb --boot build/boot-0.27-v20 --rootfs build/rootfs-final.squashfs --image build/deepos-r36s-v20-0.27-test.img --loader-donor <archr-clone-image>
python3 tools/verify-image.py --loader-donor <archr-clone-image> build/deepos-r36s-v20-0.27-test.img
python3 tools/dpflash.py --list          # номер карты, не гадать
```

Из PowerShell с правами администратора, подставив номер карты и её образ:

```powershell
.\flash-deepos.ps1 -Image build/deepos-r36s-v20-0.27-test.img -Sha256 2671df94319b334ed65db990342bbae80cb10e11d2210a7e062cd907f8f3ae29
```
