#!/usr/bin/env python3
"""Grow the last GPT partition to the real end of the card.

The image is built for a fixed size (4 GiB), but cards are bigger.  Flashing a
4 GiB GPT onto a 50 GB card leaves 45 GB unreachable: the GPT still describes a
4 GiB disk.  After the write we move the backup header to the real end of the
device, extend the last partition up to `last_usable` and fix both CRCs.

The kernel mounts ROMS using that extended entry, so the user gets the whole
card for games.  Raw devices need the same ctypes access as `dpflash`, so the
read/write primitives are reused from there.
"""
import argparse
import binascii
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dpflash  # noqa: E402  (same directory, and it only defines functions)

SECTOR = 512
GPT_SIG = b"EFI PART"
ENTRY_COUNT = 32
ENTRY_SIZE = 128
ENTRIES_SECTORS = ENTRY_COUNT * ENTRY_SIZE // SECTOR


def crc32(data):
    return binascii.crc32(data) & 0xFFFFFFFF


def header_crc(header):
    size = struct.unpack_from("<I", header, 12)[0]
    raw = bytearray(header[:size] if 92 <= size <= len(header) else header)
    raw[16:20] = b"\x00\x00\x00\x00"
    return crc32(bytes(raw))


def build_header(base, total_sectors, backup_lba, entries_lba, entries_crc):
    header = bytearray(base)
    struct.pack_into("<Q", header, 32, backup_lba)
    # last usable LBA sits right before the backup entry array, which is
    # ENTRY_COUNT*ENTRY_SIZE bytes (8 sectors for 32 entries, not 32).
    struct.pack_into("<Q", header, 48, backup_lba - ENTRIES_SECTORS - 1)
    struct.pack_into("<Q", header, 72, entries_lba)
    struct.pack_into("<I", header, 80, ENTRY_COUNT)
    struct.pack_into("<I", header, 84, ENTRY_SIZE)
    struct.pack_into("<I", header, 88, entries_crc)
    struct.pack_into("<I", header, 16, 0)
    struct.pack_into("<I", header, 16, header_crc(bytes(header)))
    return bytes(header)


def expand_target(target_path, device_bytes, verbose=True):
    """Rewrite the GPT of `target_path` so it covers `device_bytes`."""
    handle = dpflash.open_target(target_path, write=True)
    try:
        mbr = dpflash.read_at(handle, 0, SECTOR)
        if mbr[510:512] != b"\x55\xaa":
            raise SystemExit("expand: no protective MBR")
        primary = dpflash.read_at(handle, SECTOR, SECTOR)
        if primary[:8] != GPT_SIG:
            raise SystemExit("expand: no primary GPT header")
        entries = bytearray(dpflash.read_at(handle, 2 * SECTOR, ENTRIES_SECTORS * SECTOR))

        total_sectors = device_bytes // SECTOR
        backup_lba = total_sectors - 1
        entries_backup_lba = backup_lba - ENTRIES_SECTORS
        last_usable = entries_backup_lba - 1

        last_index = -1
        last_start = last_end = 0
        for i in range(ENTRY_COUNT):
            first, last = struct.unpack_from("<QQ", entries, i * ENTRY_SIZE + 32)
            if first and last:
                last_index, last_start, last_end = i, first, last
        if last_index < 0:
            raise SystemExit("expand: no partitions in the table")

        old_sectors = last_end + 1 - last_start
        new_sectors = last_usable + 1 - last_start
        if new_sectors <= old_sectors:
            raise SystemExit("expand: device is not bigger than the image")
        struct.pack_into("<Q", entries, last_index * ENTRY_SIZE + 40, last_usable)
        entries = bytes(entries)

        entries_crc = crc32(entries)
        primary = build_header(primary, total_sectors, backup_lba, 2, entries_crc)
        dpflash.write_at(handle, SECTOR, primary)
        dpflash.write_at(handle, 2 * SECTOR, entries)
        dpflash.write_at(handle, entries_backup_lba * SECTOR, entries)
        backup = build_header(primary, total_sectors, backup_lba,
                              entries_backup_lba, entries_crc)
        dpflash.write_at(handle, backup_lba * SECTOR, backup)

        if verbose:
            grew = (new_sectors - old_sectors) * SECTOR
            print(f"expand: partition {last_index + 1} grew by {grew // (1024 ** 2)} MiB "
                  f"(now {new_sectors * SECTOR // (1024 ** 2)} MiB), "
                  f"backup header at LBA {backup_lba}")
    finally:
        dpflash.close(handle)
    return last_index + 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extend the last GPT partition to the card size")
    parser.add_argument("--target", required=True)
    parser.add_argument("--size-bytes", type=int, default=0,
                        help="device size in bytes (defaults to the file size, raw devices need it)")
    args = parser.parse_args(argv)
    size = args.size_bytes or dpflash.target_size(args.target)
    expand_target(args.target, size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
