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
import struct
import subprocess
import zlib
import pathlib
import shutil
import sys

DTB_NAME = "rk3326-r36s-v20.dtb"
KERNEL_NAME = "KERNEL"
BOARD_BOOT = pathlib.Path(__file__).resolve().parents[1] / "board/r36s-v20/boot"
BOOT_SCRIPT = "boot.scr"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_extlinux(text):
    lines = [line.split(None, 1) for raw in text.splitlines()
             if (line := raw.strip()) and not line.startswith("#")]
    for command, value in (("LABEL", "DEEPoS"), ("LINUX", "/KERNEL"),
                           ("FDT", f"/dtbs/{DTB_NAME}")):
        if [command, value] not in lines:
            raise ValueError(f"extlinux.conf is missing: {command} {value}")

    appends = [line[1] for line in lines if line[0] == "APPEND" and len(line) == 2]
    if len(appends) != 1 or chr(92) in appends[0]:
        raise ValueError("extlinux.conf requires one physical APPEND line")
    args = appends[0].split()
    roots = [arg for arg in args if arg.startswith("root=")]
    if roots not in (["root=PARTLABEL=DEEPOS_A"], ["root=PARTLABEL=DEEPOS_B"]):
        raise ValueError("extlinux.conf requires a DEEPOS_A or DEEPOS_B GPT root label")
    required = {"rootfstype=squashfs", "ro", "rootwait", "console=ttyS2,1500000n8",
                "console=tty0"}
    if missing := required.difference(args):
        raise ValueError("extlinux.conf is missing: " + ", ".join(sorted(missing)))


def valid_boot_script(blob):
    if len(blob) < 72:
        return False
    header = bytearray(blob[:64])
    magic, header_crc, _, length, _, _, data_crc = struct.unpack_from(">7I", header)
    if magic != 0x27051956 or header[30] != 6 or length != len(blob) - 64:
        return False
    header[4:8] = bytes(4)
    payload = blob[64:]
    script_size, terminator = struct.unpack_from(">II", payload)
    return (zlib.crc32(header) == header_crc and zlib.crc32(payload) == data_crc
            and 0 < script_size <= len(payload) - 8 and terminator == 0
            and b"/extlinux/extlinux.conf" in payload[8:8 + script_size])


def build(kernel, dtb, out, extlinux=None, logo=None, version="0.1", extra=None,
          boot_script=None):
    kernel = pathlib.Path(kernel)
    dtb = pathlib.Path(dtb)
    out = pathlib.Path(out)

    for p, what in ((kernel, "kernel"), (dtb, "dtb")):
        if not p.is_file():
            raise SystemExit(f"{what} not found: {p}")
    if kernel.stat().st_size < 1024 * 1024:
        raise SystemExit(f"kernel looks too small ({kernel.stat().st_size} B)")

    config = pathlib.Path(extlinux or BOARD_BOOT / "extlinux/extlinux.conf").read_text(
        encoding="utf-8")
    try:
        validate_extlinux(config)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if out.exists():
        shutil.rmtree(out)
    (out / "dtbs").mkdir(parents=True)
    (out / "extlinux").mkdir()

    shutil.copyfile(kernel, out / KERNEL_NAME)
    shutil.copyfile(dtb, out / "dtbs" / DTB_NAME)

    (out / "extlinux" / "extlinux.conf").write_text(config, encoding="utf-8", newline="\n")

    files = {}
    if boot_script:
        target = out / BOOT_SCRIPT
        subprocess.run(["mkimage", "-A", "arm64", "-T", "script", "-C", "none",
                        "-n", "DEEPoS boot", "-d", str(boot_script), str(target)],
                       check=True, env=dict(os.environ, SOURCE_DATE_EPOCH="0"))
        if not valid_boot_script(target.read_bytes()):
            raise SystemExit("mkboot: invalid U-Boot boot script")
        files[BOOT_SCRIPT] = sha256_file(target)

    for item in (extra or []):
        src = pathlib.Path(item)
        if not src.is_file():
            raise SystemExit(f"extra file not found: {src}")
        if src.name in {BOOT_SCRIPT, KERNEL_NAME, "MANIFEST.json"}:
            raise SystemExit(f"reserved BOOT filename: {src.name}")
        dst = out / src.name
        shutil.copyfile(src, dst)
        files[src.name] = sha256_file(dst)

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
    ap.add_argument("--boot-script", help="U-Boot commands to package as boot.scr")
    ap.add_argument("--extlinux", default=None, help="extlinux.conf to copy")
    ap.add_argument("--logo", default=None, help="640x480 24-bit BMP splash")
    ap.add_argument("--extra", action="append", default=[],
                    help="additional file for the BOOT volume (repeatable)")
    ap.add_argument("--version", default="0.1")
    args = ap.parse_args(argv)

    manifest = build(args.kernel, args.dtb, args.out, args.extlinux, args.logo, args.version,
                     args.extra, args.boot_script)
    for rel, size in sorted(manifest["sizes"].items()):
        print(f"  {rel}: {size} B")
    print(f"{args.out}: boot tree ready (version {args.version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
