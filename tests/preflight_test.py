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
        fh.write(b"sitronix,st7703\0" + b"\x00" * (11 * 1024 * 1024))

    dtb = base / "build/kernel/rk3326-r36s-v20.dtb"
    dts = base / "test.dts"
    dts.write_text("""
/dts-v1/;
/ {
    compatible = "deepos,r36s-v20";
    display-subsystem { status = "okay"; };
    vop@ff460000 { status = "okay"; };
    dsi@ff450000 {
        status = "okay";
        panel@0 { compatible = "sitronix,st7703"; };
    };
};
""", encoding="utf-8")
    subprocess.run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o", str(dtb),
                    str(dts)], check=True)
    boot = base / "build/boot"
    (boot / "extlinux").mkdir(parents=True)
    (boot / "dtbs").mkdir(parents=True)
    shutil.copyfile(ROOT / "board/r36s-v20/boot/extlinux/extlinux.conf",
                    boot / "extlinux/extlinux.conf")
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


def test_archr_v20(paths: dict[str, Path]) -> bool:
    dtb = paths["dtb"]
    kernel = paths["kernel"]
    boot = paths["boot"]
    conf = boot / "extlinux/extlinux.conf"
    archr_conf = (ROOT / "board/r36s-v20/boot/extlinux/archr-v20.conf").read_text()

    def dt_set(node, prop, value):
        subprocess.run(["fdtput", "-t", "s", str(dtb), node, prop, value], check=True)
        shutil.copyfile(dtb, boot / "dtbs/rk3326-r36s-v20.dtb")

    dt_set("/", "compatible", "gameconsole,eeclone")
    panel = "/dsi@ff450000/panel@0"
    dt_set(panel, "compatible", "archr,generic-dsi")
    working_mode = "M clock=30000 horizontal=640,150,50,150 vertical=480,20,6,12 default=1"
    dt_set(panel, "panel_description", working_mode)
    with kernel.open("r+b") as fh:
        fh.write(b"archr,generic-dsi\0")
    conf.write_text(archr_conf)
    subprocess.run([sys.executable, str(ROOT / "tools/mkboot.py"),
                    "--kernel", str(kernel), "--dtb", str(dtb), "--out", str(boot),
                    "--extlinux", str(conf)], check=True, capture_output=True)
    result = run_preflight(paths["base"])
    ok = result.returncode == 0
    if not ok:
        print("FAIL  preflight: rejected the working Arch-R V20 profile")
        print(result.stdout, result.stderr)

    rootdir = boot / "ROOTDIR.CPIO"
    saved = rootdir.read_bytes()
    rootdir.write_bytes(b"broken")
    result = run_preflight(paths["base"])
    if result.returncode == 0 or "/root mountpoint initramfs" not in result.stdout:
        print("FAIL  preflight: accepted an invalid /root mountpoint initramfs")
        ok = False
    rootdir.write_bytes(saved)

    wrong_mode = "M clock=50000 horizontal=720,140,80,140 vertical=720,20,4,20 default=1"
    dt_set(panel, "panel_description", wrong_mode)
    result = run_preflight(paths["base"])
    if result.returncode == 0 or "640x480" not in result.stdout:
        print("FAIL  preflight: accepted the bare Arch-R 720x720 panel")
        ok = False
    dt_set(panel, "panel_description", working_mode)

    conf.write_text(archr_conf.replace(" rdinit=/__deepos_mount_root__", ""))
    result = run_preflight(paths["base"])
    if result.returncode == 0 or "rdinit" not in result.stdout:
        print("FAIL  preflight: accepted Arch-R embedded /init as PID 1")
        ok = False

    conf.write_text(archr_conf.rstrip() + " earlycon=uart8250,mmio32,0xff178000,1500000\n")
    result = run_preflight(paths["base"])
    if result.returncode == 0 or "UART clock" not in result.stdout:
        print("FAIL  preflight: accepted earlycon at 1500000 without a UART clock")
        ok = False
    return ok


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

    for node, prop, replacement, original, reason in (
        ("/vop@ff460000", "status", "disabled", "okay", "display VOP is enabled"),
        ("/dsi@ff450000/panel@0", "compatible", "unmatched,panel", "sitronix,st7703",
         "kernel supports the DTB panel"),
    ):
        def set_prop(value):
            subprocess.run(["fdtput", "-t", "s", str(paths["dtb"]), node, prop,
                            value], check=True)
            shutil.copyfile(paths["dtb"], paths["boot"] / "dtbs/rk3326-r36s-v20.dtb")
        set_prop(replacement)
        res = run_preflight(tmp)
        set_prop(original)
        if res.returncode == 0 or reason not in res.stdout:
            print(f"FAIL  preflight: accepted broken display pipeline ({reason})")
            ok = False

    with tempfile.TemporaryDirectory(prefix="preflight-archr-") as archr_tmp:
        if not test_archr_v20(make_tree(Path(archr_tmp))):
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
