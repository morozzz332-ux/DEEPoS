#!/usr/bin/env python3
"""Prepare Arch-R's open V20 hardware stack for a DeepOS root filesystem."""

import argparse
import gzip
import hashlib
import pathlib
import shutil
import struct
import subprocess
import tempfile

from v20_display import display_checks, get_string, PANEL

SECTOR = 512
BOOT_START = 16 * 1024 * 1024
BOOT_SIZE = 256 * 1024 * 1024
ARCHR_DTB = "rk3326-gameconsole-eeclone.dtb"
BOARD_DTB = "rk3326-r36s-v20.dtb"


def extract_boot(image, destination):
    opener = gzip.open if image.suffix.lower() == ".gz" else open
    with opener(image, "rb") as source:
        head = source.read(SECTOR)
        if len(head) != SECTOR or head[510:512] != b"\x55\xaa" or head[450] not in (0x0B, 0x0C):
            raise ValueError("expected the first FAT32 partition of an Arch-R clone image")
        start, sectors = struct.unpack_from("<II", head, 454)
        if (start * SECTOR, sectors * SECTOR) != (BOOT_START, BOOT_SIZE):
            raise ValueError("unexpected Arch-R clone BOOT geometry")
        source.seek(BOOT_START)
        with destination.open("wb") as out:
            remaining = BOOT_SIZE
            while remaining:
                chunk = source.read(min(remaining, 4 * 1024 * 1024))
                if not chunk:
                    raise ValueError("truncated Arch-R BOOT partition")
                out.write(chunk)
                remaining -= len(chunk)


def prepare(image, overlay, out):
    with tempfile.TemporaryDirectory(prefix="deepos-v20-") as temp:
        temp = pathlib.Path(temp)
        fat = temp / "archr-boot.fat"
        extract_boot(image, fat)
        kernel = temp / "KERNEL"
        base = temp / ARCHR_DTB
        dtb = temp / BOARD_DTB
        for source, path in (("::/KERNEL", kernel), (f"::/dtbs/{ARCHR_DTB}", base)):
            subprocess.run(["mcopy", "-i", str(fat), source, str(path)], check=True)
        blob = kernel.read_bytes()
        if (blob[56:60] != b"ARMd" or b"Linux version 6.12." not in blob
                or b"squashfs\0" not in blob):
            raise ValueError("unexpected Arch-R arm64 kernel or missing squashfs")
        subprocess.run(["fdtoverlay", "-i", str(base), "-o", str(dtb), str(overlay)],
                       check=True)
        if get_string(dtb, PANEL, "compatible") != "archr,generic-dsi":
            raise ValueError("overlay does not select the Arch-R generic DSI panel")
        if get_string(dtb, "/aliases", "serial2") != "/serial@ff178000":
            raise ValueError("unexpected UART mapping for the Arch-R V20 console")
        for ok, name in display_checks(dtb, kernel):
            if not ok:
                raise ValueError(name)
        banner = blob.split(b"Linux version ", 1)[1].split(b" ", 1)[0].decode("ascii")
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kernel, out / "Image")
        shutil.copyfile(dtb, out / BOARD_DTB)
        return banner, hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archr-image", type=pathlib.Path, required=True)
    parser.add_argument("--panel-overlay", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        version, digest = prepare(args.archr_image, args.panel_overlay, args.out)
    except (OSError, EOFError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"prepare-v20-kernel: {exc}\n")
    print(f"Arch-R Linux {version} prepared (kernel sha256={digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
