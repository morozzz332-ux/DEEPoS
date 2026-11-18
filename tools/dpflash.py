#!/usr/bin/env python3
"""DEEPoS flasher - writes an image to a card (or to a file, for tests).

Flash order matters on Windows: as soon as a valid partition table exists the
mount manager tries to mount FAT/exFAT volumes, and writing into a mounted
volume fails with `win32=5` (ERROR_ACCESS_DENIED on \\\\.\\\\PhysicalDriveN).
So the table region (protective MBR + GPT header + entry array) is written
LAST: the card stays "blank" while the payload streams in, then a single 17 KiB
write makes it bootable.

Usage:
    python3 tools/dpflash.py --image build/deepos.img --target \\\\.\\\\PhysicalDrive2
    python3 tools/dpflash.py --image build/deepos.img --target test.img --dry-run

A plain file target is supported so the whole flow is testable on the host.
"""
import argparse
import hashlib
import os
import re
import json
import pathlib
import subprocess
import sys

MIB = 1024 * 1024
CHUNK = 4 * MIB
TABLE_BYTES = 34 * 512  # protective MBR + primary GPT header + 32 entries


def sha256_file(path, limit=None):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        remaining = limit
        while True:
            size = CHUNK if remaining is None else min(CHUNK, remaining)
            if size <= 0:
                break
            chunk = handle.read(size)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return digest.hexdigest()


DISK_NUMBER_RE = re.compile(r"^\\\\\.\\PhysicalDrive(\d+)$")


def _windows_disk_size(number):
    """Ask PowerShell for the length of a physical disk.

    CreateFileW(..., GENERIC_READ) is denied for removable cards on some
    systems and GetFileSizeEx() answers 0 for raw devices, so Get-Disk is the
    reliable path here.
    """
    script = (f"(Get-Disk -Number {number}).Size")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                         capture_output=True, text=True, timeout=30)
    text = (out.stdout or "").strip().splitlines()
    if text and text[-1].isdigit():
        return int(text[-1])
    return 0


def target_size(path):
    """Size of a regular file or of a raw disk/volume device."""
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > 0:
        return size
    if os.name != "nt":
        raise SystemExit(f"dpflash: cannot determine size of {path}")

    match = DISK_NUMBER_RE.match(path)
    if match:
        size = _windows_disk_size(int(match.group(1)))
        if size:
            return size
        raise SystemExit(f"dpflash: cannot determine size of {path} "
                         f"(Get-Disk returned nothing)")

    import ctypes

    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)
    if ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            path, ctypes.byref(free), ctypes.byref(total), None) and total.value:
        return int(total.value)
    raise SystemExit(f"dpflash: cannot determine size of {path}")


def open_target(path, write):
    if os.name == "nt":
        import ctypes
        access = 0x80000000 | 0x40000000 if write else 0x80000000
        share = 0  # exclusive: nothing else may hold the device
        handle = ctypes.windll.kernel32.CreateFileW(path, access, share, None, 3, 0, None)
        if handle == -1:
            err = ctypes.windll.kernel32.GetLastError()
            raise SystemExit(f"dpflash: cannot open {path} (win32={err}); close Explorer/disk tools and retry")
        return handle

    return open(path, "r+b" if write else "rb")


def write_at(handle, offset, data):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        moved = ctypes.c_longlong(0)
        ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offset),
                                                ctypes.byref(moved), 0)
        written = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(data, len(data))
        if not ctypes.windll.kernel32.WriteFile(handle, buf, len(data),
                                                ctypes.byref(written), None):
            err = ctypes.windll.kernel32.GetLastError()
            raise SystemExit(f"dpflash: write failed at offset {offset} (win32={err})")
        if written.value != len(data):
            raise SystemExit(f"dpflash: short write at offset {offset}")
    else:
        handle.seek(offset)
        handle.write(data)


def read_at(handle, offset, size):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        moved = ctypes.c_longlong(0)
        ctypes.windll.kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offset),
                                                ctypes.byref(moved), 0)
        buf = ctypes.create_string_buffer(size)
        got = wintypes.DWORD(0)
        ctypes.windll.kernel32.ReadFile(handle, buf, size, ctypes.byref(got), None)
        return buf.raw[:got.value]

    handle.seek(offset)
    return handle.read(size)


def close(handle):
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.CloseHandle(handle)
    else:
        handle.close()


def flash(image_path, target_path, dry_run=False, defer_table=True, expected_sha=None):
    image_size = os.path.getsize(image_path)
    card_size = target_size(target_path)
    if card_size < image_size:
        raise SystemExit(f"dpflash: target is {card_size} B, image needs {image_size} B")

    digest = sha256_file(image_path)
    print(f"image   {image_path} ({image_size} B)")
    print(f"target  {target_path} ({card_size} B)")
    print(f"sha256  {digest}")
    if expected_sha and digest != expected_sha.lower():
        raise SystemExit("dpflash: image sha256 does not match --expect-sha256")
    if dry_run:
        print("dry-run: nothing written")
        return 0

    with open(image_path, "rb") as src:
        table = src.read(TABLE_BYTES)
        src.seek(max(0, image_size - 33 * 512))
        table_tail = src.read()

    handle = open_target(target_path, write=True)
    try:
        if defer_table:
            # A zeroed table means Windows does not mount anything mid-write.
            write_at(handle, 0, bytes(TABLE_BYTES))
        start = TABLE_BYTES if defer_table else 0
        with open(image_path, "rb") as src:
            src.seek(start)
            offset = start
            while offset < image_size:
                chunk = src.read(min(CHUNK, image_size - offset))
                if not chunk:
                    break
                write_at(handle, offset, chunk)
                offset += len(chunk)
                print(f"\r  written {offset * 100 // image_size}%", end="", flush=True)
        print()
        if defer_table:
            write_at(handle, 0, table)
            if table_tail:
                write_at(handle, image_size - len(table_tail), table_tail)
    finally:
        close(handle)
    print("done: table written last, card is bootable")
    return 0

def list_disks(stream=sys.stdout):
    """Show candidate cards so nobody has to guess the PhysicalDrive number."""
    if os.name == "nt":
        cmd = ["powershell", "-NoProfile", "-Command",
               "Get-Disk | Select-Object Number,FriendlyName,Size,BusType,PartitionStyle | ConvertTo-Json -Compress"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"cannot enumerate disks: {exc}", file=stream)
            return 1
        if not out:
            print("no disks reported", file=stream)
            return 1
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        print("disk  size      bus   style  model", file=stream)
        for d in sorted(data, key=lambda x: x.get("Number", 0)):
            size = float(d.get("Size") or 0) / (1024 ** 3)
            print(f'{d.get("Number"):>4}  {size:>7.1f}G  {str(d.get("BusType") or "?"):<5} '
                  f'{str(d.get("PartitionStyle") or "?"):<6} {d.get("FriendlyName") or "?"}', file=stream)
        return 0

    base = pathlib.Path("/sys/block")
    rows = []
    for entry in sorted(base.iterdir()):
        name = entry.name
        if name.startswith(("loop", "ram", "zram")):
            continue
        try:
            sectors = int((entry / "size").read_text().strip())
        except (OSError, ValueError):
            continue
        model = ""
        try:
            model = (entry / "device/model").read_text().strip()
        except OSError:
            pass
        removable = ""
        try:
            removable = (entry / "removable").read_text().strip()
        except OSError:
            pass
        rows.append((name, sectors * 512 / (1024 ** 3), model or "?", removable))
    if not rows:
        print("no block devices reported", file=stream)
        return 1
    print("dev       size      removable  model", file=stream)
    for name, size, model, removable in rows:
        print(f"/dev/{name:<8} {size:>7.1f}G  {removable or '?':<9} {model}", file=stream)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Flash a DEEPoS image to a card")
    parser.add_argument("--image", default=None)
    parser.add_argument("--target", default=None,
                        help="\\\\.\\\\PhysicalDriveN on Windows, any file path for tests")
    parser.add_argument("--list", action="store_true", help="list candidate disks and exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-defer-table", action="store_true",
                        help="write the table first (files/testing only)")
    parser.add_argument("--expect-sha256", default=None)
    args = parser.parse_args(argv)
    if args.list:
        return list_disks()
    if not args.image or not args.target:
        parser.error("--image and --target are required unless --list is used")
    return flash(args.image, args.target, dry_run=args.dry_run,
                 defer_table=not args.no_defer_table, expected_sha=args.expect_sha256)


if __name__ == "__main__":
    sys.exit(main())
