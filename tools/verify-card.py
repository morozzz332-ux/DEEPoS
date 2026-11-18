#!/usr/bin/env python3
"""Verify both GPT copies and filesystem geometry on a flashed DeepOS card.

With --image, also verify the card's byte-for-byte prefix up to the image size.
The source image may occupy only part of the device.
"""
import argparse
import hashlib
import os
import struct
import sys
from contextlib import ExitStack

import dpflash
from expand_gpt import GPT_SIG, SECTOR, read_exact, read_gpt, relocated_metadata

MIB = 1024 ** 2
EXPECTED = ["BOOT", "DEEPOS_A", "DEEPOS_B", "DATA", "ROMS"]


def compare_prefix(handle, source, start, end):
    target_sha = hashlib.sha256()
    image_sha = hashlib.sha256()
    source.seek(start)
    for offset in range(start, end, 8 * MIB):
        length = min(8 * MIB, end - offset)
        block = source.read(length)
        if len(block) != length:
            raise ValueError("source image changed size during verification")
        image_sha.update(block)
        target_sha.update(read_exact(handle, offset, length))
    return target_sha.hexdigest(), image_sha.hexdigest()


def roms_size(handle, partition):
    first, last, _ = partition
    boot = read_exact(handle, first * SECTOR, SECTOR)
    if boot[3:11] != b"EXFAT   ":
        raise ValueError("ROMS exFAT signature")
    volume_sectors, = struct.unpack_from("<Q", boot, 72)
    sector_shift = boot[108]
    if not 9 <= sector_shift <= 12:
        raise ValueError("ROMS exFAT sector size is invalid")
    volume_bytes = volume_sectors << sector_shift
    partition_bytes = (last - first + 1) * SECTOR
    if volume_bytes != partition_bytes:
        raise ValueError(f"ROMS exFAT volume length {volume_bytes} bytes differs "
                         f"from partition size {partition_bytes} bytes")
    heap_start, cluster_count = struct.unpack_from("<II", boot, 88)
    cluster_shift = boot[109]
    if (cluster_shift > 25 - sector_shift or not heap_start or not cluster_count
            or heap_start + (cluster_count << cluster_shift) > volume_sectors):
        raise ValueError("ROMS exFAT cluster heap is outside the volume")
    return volume_bytes


def verify(handle, size, source, image_size):
    gpt = read_gpt(handle, size)
    gpt_size = (gpt.primary.alternate_lba + 1) * SECTOR
    if gpt_size < size:
        if read_exact(handle, size - SECTOR, SECTOR).startswith(GPT_SIG):
            raise ValueError("conflicting GPT header at the physical device end")
        print(f"  ok   backup GPT at image boundary ({gpt_size} of {size} bytes)")
    print("  ok   protective MBR and both GPT headers and partition arrays")

    labels = [name.decode("utf-16-le").split("\0", 1)[0] for _, _, name in gpt.partitions]
    if labels != EXPECTED:
        raise ValueError(f"partition labels/order: expected {EXPECTED}, got {labels}")
    boot, sys_a, sys_b, data, roms = gpt.partitions

    def sector(partition, index=0):
        first, last, _ = partition
        if first + index > last:
            raise ValueError("partition is too short to contain a filesystem")
        return read_exact(handle, (first + index) * SECTOR, SECTOR)

    if sector(boot)[82:87] != b"FAT32":
        raise ValueError("BOOT FAT32 signature")
    if sector(sys_a)[:4] != b"hsqs":
        raise ValueError("SYS_A squashfs signature")
    if sector(sys_b)[:4] != b"hsqs":
        raise ValueError("SYS_B squashfs signature")
    if sector(data, 2)[56:58] != b"\x53\xef":
        raise ValueError("DATA ext4 signature")
    print(f"  ok   filesystems, ROMS exFAT volume length {roms_size(handle, roms)} bytes")

    if source is not None:
        if gpt_size == image_size:
            actual, expected = compare_prefix(handle, source, 0, image_size)
            compared = "card prefix"
        elif gpt_size == size and image_size < size:
            read_gpt(source, image_size, image_bytes=image_size)
            source_head = read_exact(source, 0, 34 * SECTOR)
            head, tail = relocated_metadata(source_head, image_size, size)
            if (read_exact(handle, 0, len(head)) != head
                    or read_exact(handle, size - len(tail), len(tail)) != tail):
                raise ValueError("physical GPT differs from the relocated image GPT")
            actual, expected = compare_prefix(handle, source, len(head), image_size - len(tail))
            print("  ok   relocated primary and backup GPT match the image layout")
            compared = "card payload"
        else:
            raise ValueError("GPT boundary does not match the image or the device")
        if actual != expected:
            raise ValueError(f"{compared} SHA-256 mismatch (card {actual}, image {expected})")
        print(f"  ok   {compared} matches the image (SHA-256 {actual})")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify a flashed DeepOS card")
    parser.add_argument("--target", required=True)
    parser.add_argument("--image", help="compare the written prefix with this image file")
    args = parser.parse_args(argv)

    try:
        size = dpflash.target_size(args.target)
        with ExitStack() as stack:
            source = stack.enter_context(open(args.image, "rb")) if args.image else None
            image_size = os.fstat(source.fileno()).st_size if source is not None else None
            if image_size is not None and not 0 < image_size <= size:
                raise ValueError(f"image length {image_size} bytes exceeds the card size or is zero")
            handle = dpflash.open_target(args.target, write=False)
            stack.callback(dpflash.close, handle)
            verify(handle, size, source, image_size)
    except (OSError, ValueError) as exc:
        print(f"  FAIL {exc}", file=sys.stderr)
        print("FAIL  card: verification failed")
        return 1

    print("PASS  card: verification complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
