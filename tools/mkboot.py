#!/usr/bin/env python3
"""Assemble the DEEPoS BOOT partition tree.

This mirrors what `make image` puts into the FAT32 BOOT partition and what the
device needs for U-Boot's distro boot: the kernel image, the board DTB, the
extlinux entry and the boot splash.

Usage:
    mkboot.py --kernel <Image> --dtb <rk3326-r36s-v20.dtb> --out <dir>
              [--extlinux board/r36s-v20/boot/extlinux/extlinux.conf]
              [--logo branding/deepos-boot.bmp] [--version 0.1]

Layout produced:
    <out>/KERNEL                     uncompressed arm64 Image, name expected by extlinux
    <out>/dtbs/rk3326-r36s-v20.dtb   board device tree
    <out>/extlinux/extlinux.conf     boot entry (LABEL DEEPoS)
    <out>/logo.bmp                   640x480 24-bit U-Boot splash (optional)
    <out>/MANIFEST.json              sha256 + sizes, used by tests and by update
"""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys

DTB_NAME = "rk3326-r36s-v20.dtb"
KERNEL_NAME = "KERNEL"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_extlinux(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    need = ["LABEL DEEPoS", "LINUX /KERNEL", f"FDT /dtbs/{DTB_NAME}"]
    missing = [n for n in need if n not in text]
    if missing:
        raise SystemExit(f"extlinux.conf is missing: {', '.join(missing)}")
    return text


def build(kernel, dtb, out, extlinux=None, logo=None, version="0.1"):
    kernel = pathlib.Path(kernel)
    dtb = pathlib.Path(dtb)
    out = pathlib.Path(out)

    for p, what in ((kernel, "kernel"), (dtb, "dtb")):
        if not p.is_file():
            raise SystemExit(f"{what} not found: {p}")
    if kernel.stat().st_size < 1024 * 1024:
        raise SystemExit(f"kernel looks too small ({kernel.stat().st_size} B)")

    if out.exists():
        shutil.rmtree(out)
    (out / "dtbs").mkdir(parents=True)
    (out / "extlinux").mkdir()

    shutil.copyfile(kernel, out / KERNEL_NAME)
    shutil.copyfile(dtb, out / "dtbs" / DTB_NAME)

    if extlinux:
        text = check_extlinux(extlinux)
        (out / "extlinux" / "extlinux.conf").write_text(text, encoding="utf-8")
    else:
        (out / "extlinux" / "extlinux.conf").write_text(
            "LABEL DEEPoS\n    LINUX /KERNEL\n"
            f"    FDT /dtbs/{DTB_NAME}\n"
            "    APPEND root=LABEL=DEEPOS_A rootfstype=squashfs ro rootwait"
            " console=ttyS2,1500000n8 console=tty0 loglevel=3 quiet\n",
            encoding="utf-8",
        )

    files = {}
    if logo:
        logo = pathlib.Path(logo)
        if not logo.is_file():
            raise SystemExit(f"logo not found: {logo}")
        shutil.copyfile(logo, out / "logo.bmp")
        files["logo.bmp"] = sha256_file(out / "logo.bmp")

    for rel in (KERNEL_NAME, f"dtbs/{DTB_NAME}", "extlinux/extlinux.conf"):
        files[rel] = sha256_file(out / rel)

    manifest = {
        "version": version,
        "board": "r36s-v20",
        "files": files,
        "sizes": {rel: (out / rel).stat().st_size for rel in files},
    }
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description="assemble the DEEPoS BOOT tree")
    ap.add_argument("--kernel", required=True, help="arm64 Image")
    ap.add_argument("--dtb", required=True, help="compiled board dtb")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--extlinux", default=None, help="extlinux.conf to copy")
    ap.add_argument("--logo", default=None, help="640x480 24-bit BMP splash")
    ap.add_argument("--version", default="0.1")
    args = ap.parse_args(argv)

    manifest = build(args.kernel, args.dtb, args.out, args.extlinux, args.logo, args.version)
    for rel, size in sorted(manifest["sizes"].items()):
        print(f"  {rel}: {size} B")
    print(f"{args.out}: boot tree ready (version {args.version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
