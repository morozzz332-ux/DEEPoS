#!/usr/bin/env python3
"""Extract the Rockchip boot chain (idbloader.img, u-boot.itb) from a released
Rockchip-style disk image (gz).

Why this exists: DEEPoS builds everything above the bootloader itself, but RK3326
has no mainline U-Boot port. Until our own vendor-fork build lands, the firmware
can boot with the loaders shipped in a known, pinned reference image (Arch-R for
R36S clones). The extracted blobs are recorded with their SHA-256 and the source
image digest, so the exception is auditable and replaceable at any time.

Layout of the Rockchip boot chain inside the image:
    idbloader.img  at 32 KiB (sector 64)
    u-boot.itb     at  8 MiB (sector 16384)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path

IDB_OFFSET = 32 * 1024
ITB_OFFSET = 8 * 1024 * 1024
ITB_SCAN = 8 * 1024 * 1024  # look for the FIT header inside this window


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_trailing_zeros(data: bytes) -> bytes:
    end = len(data)
    while end > 0 and data[end - 1] == 0:
        end -= 1
    return data[:end]


def read_at(gz, offset: int, length: int) -> bytes:
    """Stream a gzip file up to offset+length and return the requested slice."""
    remaining = offset + length
    head = bytearray()
    while remaining > 0:
        chunk = gz.read(min(1 << 20, remaining))
        if not chunk:
            break
        head += chunk
        remaining -= len(chunk)
    return bytes(head[offset:offset + length])


def extract(image: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(image, "rb") as gz:
        idb_raw = read_at(gz, IDB_OFFSET, ITB_OFFSET - IDB_OFFSET)
    idbloader = strip_trailing_zeros(idb_raw)
    if not idbloader:
        raise SystemExit("idbloader region is empty - wrong image?")
    # Rockchip idbloader starts with the "RKn" magic inside the TPL/SPL header.
    if b"RK32" not in idbloader[:256] and b"RK3" not in idbloader[:256]:
        raise SystemExit("idbloader magic not found at 32 KiB - wrong layout?")

    with gzip.open(image, "rb") as gz:
        itb_raw = read_at(gz, ITB_OFFSET, ITB_SCAN)
    magic = struct.unpack(">I", itb_raw[:4])[0]
    if magic != 0xD00DFEED:
        raise SystemExit(f"FIT magic missing at 8 MiB (got 0x{magic:08x})")
    total = struct.unpack(">I", itb_raw[4:8])[0]
    if not (1024 < total <= ITB_SCAN):
        raise SystemExit(f"implausible FIT size {total}")
    itb = itb_raw[:total]

    (out_dir / "idbloader.img").write_bytes(idbloader)
    (out_dir / "u-boot.itb").write_bytes(itb)
    meta = {
        "source_image": image.name,
        "source_sha256": file_sha256(image),
        "idbloader_bytes": len(idbloader),
        "idbloader_sha256": hashlib.sha256(idbloader).hexdigest(),
        "uboot_itb_bytes": len(itb),
        "uboot_itb_sha256": hashlib.sha256(itb).hexdigest(),
        "idbloader_offset": IDB_OFFSET,
        "uboot_itb_offset": ITB_OFFSET,
        "note": "extracted from a pinned reference image; replace with own vendor-fork build",
    }
    (out_dir / "BUILD.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="extract Rockchip loaders out of a gz image")
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"no such image: {args.image}")
    meta = extract(args.image, args.out)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
