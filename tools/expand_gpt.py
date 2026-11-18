#!/usr/bin/env python3
"""Relocate the backup GPT to the device end without resizing filesystems."""
import argparse
import binascii
from dataclasses import dataclass
import struct
import sys

import dpflash

SECTOR = 512
GPT_SIG = b"EFI PART"
GPT_HEADER = struct.Struct("<8sIIIIQQQQ16sQIII")


def crc32(data):
    return binascii.crc32(data) & 0xFFFFFFFF


def header_crc(header, size):
    raw = bytearray(header[:size])
    struct.pack_into("<I", raw, 16, 0)
    return crc32(raw)


@dataclass
class Header:
    raw: bytes
    size: int
    alternate_lba: int
    first_usable: int
    last_usable: int
    disk_guid: bytes
    entries_lba: int
    entries_length: int
    entries_crc: int

    @property
    def entries_sectors(self):
        return self.entries_length // SECTOR


@dataclass
class Gpt:
    mbr: bytes
    primary: Header
    backup: Header
    entries: bytes
    partitions: list


def read_exact(handle, offset, size):
    data = dpflash.read_at(handle, offset, size)
    if len(data) != size:
        raise OSError(f"short read at byte {offset}: got {len(data)} of {size} bytes")
    return data


def read_header(handle, lba, name):
    return parse_header(read_exact(handle, lba * SECTOR, SECTOR), lba, name)


def parse_header(raw, lba, name):
    (sig, revision, size, crc, reserved, current, alternate, first, last,
     disk_guid, entries_lba, entry_count, entry_size, entries_crc) = GPT_HEADER.unpack_from(raw)
    if sig != GPT_SIG:
        raise ValueError(f"{name} GPT header signature")
    if not (GPT_HEADER.size <= size <= SECTOR) or revision != 0x10000 or reserved:
        raise ValueError(f"{name} GPT header size or revision")
    if header_crc(raw, size) != crc:
        raise ValueError(f"{name} GPT header CRC")
    if current != lba:
        raise ValueError(f"{name} GPT header LBA: stored {current}, read at {lba}")
    # Older DeepOS images used 32 entries. Newly built images reserve the
    # standard 16 KiB array of 128 entries.
    if entry_count not in (32, 128) or entry_size != 128:
        raise ValueError(f"{name} GPT partition entry geometry")
    return Header(raw, size, alternate, first, last, disk_guid, entries_lba,
                  entry_count * entry_size, entries_crc)


def read_entries(handle, header, name):
    entries = read_exact(handle, header.entries_lba * SECTOR, header.entries_length)
    if crc32(entries) != header.entries_crc:
        raise ValueError(f"{name} partition entries CRC")
    return entries


def read_gpt(handle, device_bytes, image_bytes=None):
    """Validate both GPT copies and return the table within the declared disk boundary."""
    if device_bytes % SECTOR or device_bytes < 3 * SECTOR:
        raise ValueError("device size must be a multiple of 512 bytes and contain a GPT")
    disk_end = device_bytes // SECTOR - 1
    mbr = read_exact(handle, 0, SECTOR)
    if mbr[510:512] != b"\x55\xaa" or mbr[450] != 0xEE:
        raise ValueError("protective MBR signature or type")

    primary = read_header(handle, 1, "primary")
    backup_lba = primary.alternate_lba
    if not (1 < backup_lba <= disk_end):
        raise ValueError(f"primary GPT alternate LBA {backup_lba} is outside the device")
    if image_bytes is not None and (backup_lba + 1) * SECTOR != image_bytes:
        raise ValueError(f"primary GPT alternate LBA {backup_lba} does not match the image boundary")
    if struct.unpack_from("<II", mbr, 454) != (1, min(backup_lba, 0xFFFFFFFF)):
        raise ValueError("protective MBR span does not cover the GPT")

    backup = read_header(handle, backup_lba, "backup")
    if backup.alternate_lba != 1:
        raise ValueError(f"backup GPT alternate LBA is {backup.alternate_lba}, expected 1")
    if (primary.first_usable, primary.last_usable, primary.disk_guid, primary.entries_length) != (
            backup.first_usable, backup.last_usable, backup.disk_guid, backup.entries_length):
        raise ValueError("primary and backup GPT geometry or disk GUID differs")
    if not (2 <= primary.entries_lba <= primary.first_usable - primary.entries_sectors
            and primary.first_usable <= primary.last_usable < backup.entries_lba
            <= backup_lba - backup.entries_sectors):
        raise ValueError("GPT usable range or partition array LBAs are invalid")

    entries = read_entries(handle, primary, "primary")
    if entries != read_entries(handle, backup, "backup"):
        raise ValueError("primary and backup GPT partition entries differ")
    partitions = []
    for index, offset in enumerate(range(0, len(entries), 128), start=1):
        entry = entries[offset:offset + 128]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        if not primary.first_usable <= first <= last <= primary.last_usable:
            raise ValueError(f"partition {index} lies outside the GPT usable range")
        partitions.append((first, last, entry[56:128]))

    previous_end = primary.first_usable - 1
    for first, last, _ in sorted(partitions):
        if first <= previous_end:
            raise ValueError("GPT partitions overlap")
        previous_end = last
    return Gpt(mbr, primary, backup, entries, partitions)


def build_header(base, current_lba, alternate_lba, last_usable, entries_lba):
    header = bytearray(base.raw)
    struct.pack_into("<QQ", header, 24, current_lba, alternate_lba)
    struct.pack_into("<Q", header, 48, last_usable)
    struct.pack_into("<Q", header, 72, entries_lba)
    struct.pack_into("<I", header, 16, header_crc(header, base.size))
    return bytes(header)


def _relocated_tables(mbr, primary, backup, entries, device_bytes):
    if device_bytes % SECTOR:
        raise ValueError("device size must be aligned to a sector")
    backup_lba = device_bytes // SECTOR - 1
    entries_lba = backup_lba - primary.entries_sectors
    last_usable = entries_lba - 1
    new_primary = build_header(primary, 1, backup_lba, last_usable,
                               primary.entries_lba)
    new_backup = build_header(backup, backup_lba, 1, last_usable, entries_lba)
    mbr = bytearray(mbr)
    struct.pack_into("<I", mbr, 458, min(backup_lba, 0xFFFFFFFF))
    return bytes(mbr) + new_primary, entries + new_backup


def relocated_metadata(head, source_size, device_size):
    """Build physical GPT buffers for a larger raw disk from a standard image."""
    if source_size % SECTOR or device_size <= source_size:
        raise ValueError("GPT relocation requires a larger device")
    if len(head) != 34 * SECTOR or head[450] != 0xEE or head[510:512] != b"\x55\xaa":
        raise ValueError("image has no standard protective MBR and GPT")
    primary = parse_header(head[SECTOR:2 * SECTOR], 1, "image primary")
    entries = head[2 * SECTOR:]
    source_last = source_size // SECTOR - 1
    if (primary.entries_lba != 2 or len(entries) != primary.entries_length
            or crc32(entries) != primary.entries_crc
            or primary.alternate_lba != source_last
            or not 34 <= primary.first_usable <= primary.last_usable < source_last - 32
            or struct.unpack_from("<II", head, 454) != (1, min(source_last, 0xFFFFFFFF))):
        raise ValueError("image has invalid source GPT geometry")
    new_head, new_tail = _relocated_tables(head[:SECTOR], primary, primary,
                                           entries, device_size)
    return new_head + entries, new_tail


def expand_target(target_path, device_bytes, verbose=True):
    """Use the device's full GPT range while preserving all partition entries."""
    handle = dpflash.open_target(target_path, write=True)
    try:
        gpt = read_gpt(handle, device_bytes)
        if not gpt.partitions:
            raise ValueError("GPT contains no partitions")
        backup_lba = device_bytes // SECTOR - 1
        if gpt.primary.alternate_lba == backup_lba:
            if verbose:
                print(f"expand: backup GPT already at device end (LBA {backup_lba})")
            return

        new_head, new_tail = _relocated_tables(gpt.mbr, gpt.primary, gpt.backup,
                                               gpt.entries, device_bytes)
        # Make the new backup durable before the primary references it.
        dpflash.write_at(handle, device_bytes - len(new_tail), new_tail, "relocate backup GPT")
        dpflash.flush(handle, "relocate backup GPT")
        dpflash.write_at(handle, 0, new_head, "publish relocated primary GPT")
        dpflash.flush(handle, "publish relocated primary GPT")
        written = read_gpt(handle, device_bytes, image_bytes=device_bytes)
        if written.entries != gpt.entries or written.primary.last_usable != backup_lba - gpt.backup.entries_sectors - 1:
            raise ValueError("GPT read-back mismatch after relocation")
    finally:
        dpflash.close(handle)
    if verbose:
        print(f"expand: backup GPT relocated to LBA {backup_lba}, partition sizes preserved")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Relocate the backup GPT to the device end")
    parser.add_argument("--target", required=True)
    parser.add_argument("--size-bytes", type=int,
                        help="require the device to have this size in bytes")
    args = parser.parse_args(argv)
    try:
        size = dpflash.target_size(args.target)
        if args.size_bytes is not None and args.size_bytes != size:
            raise ValueError(f"device has {size} bytes, expected {args.size_bytes}")
        expand_target(args.target, size)
    except (OSError, ValueError) as exc:
        print(f"expand: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
