#!/usr/bin/env python3
"""tools/preflight.py must say GO on a complete tree and NO-GO on a broken one."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/w")
PREFLIGHT = ROOT / "tools/preflight.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_tree(base: Path) -> dict[str, Path]:
    kernel = base / "build/kernel/Image"
    kernel.parent.mkdir(parents=True)
    with kernel.open("wb") as fh:
        fh.write(b"\x00" * (11 * 1024 * 1024))

    dtb = base / "build/kernel/rk3326-r36s-v20.dtb"
    dtb.write_bytes(b"\xd0\x0d\xfe\xed" + b"deepos,r36s-v20\x00sitronix,st7703\x00" + b"\x00" * 64)

    boot = base / "build/boot"
    (boot / "extlinux").mkdir(parents=True)
    (boot / "dtbs").mkdir(parents=True)
    (boot / "extlinux/extlinux.conf").write_text(
        "LABEL DEEPoS\n"
        "  LINUX /KERNEL\n"
        "  FDT /dtbs/rk3326-r36s-v20.dtb\n"
        "  APPEND root=LABEL=DEEPOS_A\n",
        encoding="utf-8")
    shutil.copyfile(kernel, boot / "KERNEL")
    shutil.copyfile(dtb, boot / "dtbs/rk3326-r36s-v20.dtb")
    (boot / "MANIFEST.json").write_text(json.dumps(
        {"version": "test", "board": "r36s-v20",
         "files": {"KERNEL": sha256(boot / "KERNEL")}}), encoding="utf-8")

    stage = base / "stage"
    for rel in ("sbin", "bin", "usr/bin", "etc/init.d"):
        (stage / rel).mkdir(parents=True, exist_ok=True)
    os.symlink("../bin/busybox", stage / "sbin/init")
    for rel in ("bin/busybox", "usr/bin/launcher", "usr/bin/modd",
                "usr/bin/saved", "usr/bin/updatr"):
        (stage / rel).write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    (stage / "etc/init.d/rcS").write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    os.chmod(stage / "etc/init.d/rcS", 0o755)
    (stage / "etc/inittab").write_text("::respawn:/usr/bin/launcher\n", encoding="utf-8")
    (stage / "etc/os-release").write_text('NAME="DEEPoS"\n', encoding="utf-8")

    rootfs = base / "build/rootfs.squashfs"
    subprocess.run(["mksquashfs", str(stage), str(rootfs), "-noappend", "-quiet",
                    "-no-progress", "-comp", "zstd"], check=True)

    loader = base / "build/uboot"
    loader.mkdir(parents=True)
    (loader / "idbloader.img").write_bytes(b"\x55" * 4096)
    (loader / "u-boot.itb").write_bytes(b"\xaa" * 8192)

    return {"base": base, "boot": boot, "dtb": dtb, "kernel": kernel,
            "rootfs": rootfs, "loader": loader}


def run_preflight(base: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PREFLIGHT), "--root", str(base), "--skip-image"],
        capture_output=True, text=True)


def main() -> int:
    if not PREFLIGHT.is_file():
        print("FAIL  preflight: tool missing")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="preflight-"))
    paths = make_tree(tmp)
    ok = True

    res = run_preflight(tmp)
    if res.returncode != 0 or "PREFLIGHT: GO" not in res.stdout:
        print(f"FAIL  preflight: complete tree rejected (rc={res.returncode})")
        print(res.stdout)
        print(res.stderr)
        ok = False
    for needle in ("dtb carries compatible deepos,r36s-v20",
                   "fdt file exists: rk3326-r36s-v20.dtb",
                   "BOOT/KERNEL sha256 matches manifest",
                   "rootfs has usr/bin/launcher",
                   "rcS is executable"):
        if needle not in res.stdout:
            print(f"FAIL  preflight: missing check {needle!r}")
            ok = False

    # the classic mistake: extlinux points at a dtb that is not in BOOT
    os.rename(paths["boot"] / "dtbs/rk3326-r36s-v20.dtb",
              paths["boot"] / "dtbs/renamed.dtb")
    res = run_preflight(tmp)
    if res.returncode == 0 or "PREFLIGHT: NO-GO" not in res.stdout:
        print(f"FAIL  preflight: missing fdt accepted (rc={res.returncode})")
        ok = False
    if "fdt file exists" not in res.stdout:
        print("FAIL  preflight: does not report the missing fdt")
        ok = False

    # a rootfs without launcher must be rejected too
    os.rename(paths["boot"] / "dtbs/renamed.dtb",
              paths["boot"] / "dtbs/rk3326-r36s-v20.dtb")
    stage = tmp / "stage"
    (stage / "usr/bin/launcher").unlink()
    subprocess.run(["mksquashfs", str(stage), str(paths["rootfs"]), "-noappend",
                    "-quiet", "-no-progress", "-comp", "zstd"], check=True)
    res = run_preflight(tmp)
    if res.returncode == 0 or "rootfs has usr/bin/launcher" not in res.stdout:
        print("FAIL  preflight: rootfs without launcher accepted")
        ok = False

    print("PASS  preflight: complete tree is GO, missing fdt and missing launcher are NO-GO"
          if ok else "FAIL  preflight checks")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
