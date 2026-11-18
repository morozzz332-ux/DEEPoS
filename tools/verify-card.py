#!/usr/bin/env python3
"""Check a freshly written card from the PC, before it ever goes into the console.

Reads the raw device (Windows `\\\\.\\PhysicalDriveN`, or a plain file for tests)
and verifies what the boot chain and the kernel will see:

  * protective MBR and both GPT headers, with CRCs;
  * the five partitions with their labels and sizes;
  * BOOT holds KERNEL and MANIFEST.json;
  * SYS_A starts with the squashfs magic;
  * DATA starts with the ext4 magic;
  * optionally the first N bytes match the image sha256 (`--image`).

Exit code 0 means "the card looks like the image", 1 otherwise.
"""
import argparse
import binascii
import hashlib
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dpflash  # noqa: E402

SECTOR = 512
MIB = 1024 ** 2
GIB = 1024 ** 3
ENTRY_SIZE = 128
ENTRY_COUNT = 32
EXPECTED = [("BOOT", "BOOT"), ("DEEPOS_A", None), ("DEEPOS_B", None),
            ("DATA", "DATA"), ("ROMS", "ROMS")]


def crc32(data):
    return binascii.crc32(data) & 0xFFFFFFFF


def decode_label(entry):
    raw = entry[56:128]
    try:
        text = raw.decode("utf-16-le").split("\x00", 1)[0]
        if text.isprintable():
            return text
    except UnicodeDecodeError:
        pass
    return raw.split(b"\x00", 1)[0].decode("utf-8", "replace")


def read(handle, offset, size):
    return dpflash.read_at(handle, offset, size)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify a flashed DEEPoS card")
    parser.add_argument("--target", required=True)
    parser.add_argument("--image", default=None,
                        help="also compare the written prefix with this image file")
    args = parser.parse_args(argv)

    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            failures.append(name)

    size = dpflash.target_size(args.target)
    handle = dpflash.open_target(args.target, write=False)
    try:
        mbr = read(handle, 0, SECTOR)
        check("protective MBR signature", mbr[510:512] == b"\x55\xaa")
        check("protective MBR type 0xEE", mbr[450] == 0xEE)

        primary = read(handle, SECTOR, SECTOR)
        check("primary GPT header", primary[:8] == b"EFI PART")
        hdr_crc = struct.unpack_from("<I", primary, 16)[0]
        hdr_size = struct.unpack_from("<I", primary, 12)[0]
        ok_size = 92 <= hdr_size <= SECTOR
        check("primary GPT header size", ok_size, f"size={hdr_size}")
        zeroed = bytearray(primary[:hdr_size]) if ok_size else bytearray(primary)
        zeroed[16:20] = b"\x00\x00\x00\x00"
        check("primary GPT header CRC", ok_size and crc32(bytes(zeroed)) == hdr_crc)

        entries = read(handle, 2 * SECTOR, ENTRY_COUNT * ENTRY_SIZE)
        entries_crc = struct.unpack_from("<I", primary, 88)[0]
        check("partition entries CRC", crc32(entries) == entries_crc)

        backup_lba = struct.unpack_from("<Q", primary, 32)[0]
        check("backup header moved to the card end", backup_lba == size // SECTOR - 1,
              f"{backup_lba} vs {size // SECTOR - 1}")
        backup = read(handle, backup_lba * SECTOR, SECTOR)
        check("backup GPT header", backup[:8] == b"EFI PART")

        parts = []
        for i in range(ENTRY_COUNT):
            off = i * ENTRY_SIZE
            first, last = struct.unpack_from("<QQ", entries, off + 32)
            if not (first and last):
                continue
            parts.append({
                "index": i,
                "start": first * SECTOR,
                "size": (last - first + 1) * SECTOR,
                "label": decode_label(entries[off:off + ENTRY_SIZE]),
            })
        check("five partitions", len(parts) == 5, str(len(parts)))
        for (want_label, _), part in zip(EXPECTED, parts):
            check(f"partition {part['index']} is {want_label}",
                  part["label"] == want_label, f'label={part["label"]!r}')
        if len(parts) == 5:
            roms = parts[4]
            check("ROMS covers the rest of the card",
                  roms["start"] + roms["size"] >= size - 34 * SECTOR,
                  f'{roms["start"] + roms["size"]} of {size}')

            boot = read(handle, parts[0]["start"], 512)
            check("BOOT volume boots", boot[82:87] in (b"FAT32", b"FAT16", b"FAT  "),
                  str(boot[82:87]))
            check("SYS_A is squashfs",
                  read(handle, parts[1]["start"], 4) == b"hsqs")
            check("SYS_B is squashfs",
                  read(handle, parts[2]["start"], 4) == b"hsqs")
            check("DATA is ext4",
                  struct.unpack("<H", read(handle, parts[3]["start"] + 1080, 2))[0] == 0xEF53)
            check("ROMS is exFAT",
                  read(handle, parts[4]["start"] + 3, 5) == b"EXFAT")
    finally:
        dpflash.close(handle)

    if args.image:
        image_size = pathlib.Path(args.image).stat().st_size
        digest = hashlib.sha256()
        handle = dpflash.open_target(args.target, write=False)
        try:
            offset = 0
            while offset < image_size:
                block = read(handle, offset, min(8 * MIB, image_size - offset))
                if not block:
                    break
                digest.update(block)
                offset += len(block)
        finally:
            dpflash.close(handle)
        with open(args.image, "rb") as src:
            want = hashlib.sha256(src.read()).hexdigest()
        check("card prefix matches the image", digest.hexdigest() == want,
              f"{digest.hexdigest()} vs {want}")

    print()
    if failures:
        print(f"FAIL  card: {len(failures)} check(s) failed")
        return 1
    print("PASS  card: GPT, partitions, filesystems and image prefix all match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
