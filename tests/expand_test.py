#!/usr/bin/env python3
"""Relocating GPT on a larger target preserves the existing filesystems."""
import hashlib
import pathlib
import struct
import sys
import tempfile
import zlib

from verify_card_test import MIB, PY, SECTOR, build_image, flash, run


def gpt_state(path):
    sectors = path.stat().st_size // SECTOR
    with path.open("rb") as handle:
        mbr = handle.read(SECTOR)
        primary = handle.read(SECTOR)
        handle.seek((sectors - 1) * SECTOR)
        backup = handle.read(SECTOR)
        arrays = []
        headers = []
        for header in (primary, backup):
            raw = bytearray(header)
            stored_crc = struct.unpack_from("<I", raw, 16)[0]
            size = struct.unpack_from("<I", raw, 12)[0]
            struct.pack_into("<I", raw, 16, 0)
            headers.append((header[:8], stored_crc == zlib.crc32(raw[:size]),
                            struct.unpack_from("<QQ", raw, 24)))
            entries_lba, count, width, stored_crc = struct.unpack_from("<QIII", header, 72)
            handle.seek(entries_lba * SECTOR)
            entries = handle.read(count * width)
            arrays.append((entries, stored_crc == zlib.crc32(entries)))
        entries = arrays[0][0]
        parts = [struct.unpack_from("<QQ", entries, index * width + 32) for index in range(5)]
    return {
        "mbr_size": struct.unpack_from("<I", mbr, 458)[0],
        "headers": headers,
        "arrays": arrays,
        "parts": parts,
        "last_usable": struct.unpack_from("<Q", primary, 48)[0],
    }


def partition_digests(path, parts):
    with path.open("rb") as handle:
        digests = []
        for first, last in parts:
            handle.seek(first * SECTOR)
            digest = hashlib.sha256()
            remaining = (last - first + 1) * SECTOR
            while remaining:
                chunk = handle.read(min(remaining, MIB))
                if not chunk:
                    raise ValueError("incomplete filesystem in image")
                digest.update(chunk)
                remaining -= len(chunk)
            digests.append(digest.hexdigest())
        return digests


def exfat_sectors(path, start_lba):
    with path.open("rb") as handle:
        handle.seek(start_lba * SECTOR)
        boot = handle.read(SECTOR)
    return struct.unpack_from("<Q", boot, 72)[0]


def check_relocation(work):
    failures = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            failures.append(name)

    image = build_image(work)
    before = gpt_state(image)
    original = partition_digests(image, before["parts"])
    expand = [PY, "tools/expand_gpt.py", "--target"]
    card_size = image.stat().st_size + 5 * MIB
    card = flash(image, work / "larger.img", card_size)
    run(expand + [str(card)])
    after = gpt_state(card)
    last_lba = card_size // SECTOR - 1
    check("protective MBR covers the target", after["mbr_size"] == last_lba)
    check("primary and backup headers have valid CRCs and reciprocal LBAs",
          after["headers"] == [(b"EFI PART", True, (1, last_lba)),
                               (b"EFI PART", True, (last_lba, 1))])
    check("both GPT arrays have valid CRCs and match the original",
          after["arrays"] == [(before["arrays"][0][0], True)] * 2)
    check("all partition bounds are preserved", before["parts"] == after["parts"])
    check("all filesystems are byte-identical after relocation",
          original == partition_digests(card, before["parts"]))
    run([PY, "tools/verify-card.py", "--target", str(card)])

    exact = flash(image, work / "exact.img", image.stat().st_size)
    out = run(expand + [str(exact)])
    check("exact-size target is accepted", "expand:" in out and "already" in out)
    check("exact-size target remains byte-identical",
          gpt_state(exact) == before and partition_digests(exact, before["parts"]) == original)

    larger = work / "fresh"
    larger.mkdir()
    full_image = build_image(larger, card_size // MIB)
    full_gpt = gpt_state(full_image)
    roms_start, roms_end = full_gpt["parts"][-1]
    volume_sectors = exfat_sectors(full_image, roms_start)
    check("fresh larger image fills the device and stops ROMS before backup GPT",
          full_image.stat().st_size == card_size and roms_end == full_gpt["last_usable"])
    check("fresh larger image has exFAT capacity matching the partition",
          volume_sectors == roms_end - roms_start + 1
          and volume_sectors - exfat_sectors(image, before["parts"][-1][0]) == 5 * MIB // SECTOR)
    run([PY, "tools/verify-card.py", "--target", str(full_image)])

    empty = work / "card-empty.img"
    with empty.open("wb") as handle:
        handle.truncate(64 * MIB)
    run(expand + [str(empty)], expect=1)

    if failures:
        print(f"FAIL  expand: {len(failures)} check(s) failed")
        return 1
    print("PASS  expand: GPT relocation preserves partition bounds and contents")
    return 0


def main():
    with tempfile.TemporaryDirectory(prefix="deepos-expand-") as directory:
        return check_relocation(pathlib.Path(directory))


if __name__ == "__main__":
    sys.exit(main())
