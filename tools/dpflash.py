#!/usr/bin/env python3
"""Flash a DEEPoS image to a prepared Windows card or a regular test file.

On Windows, flash-deepos.ps1 validates the image and clears the selected disk
before invoking this writer. Keep the raw handle open and defer both GPT copies
until the payload is complete so Windows cannot mount a writable volume.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
import pathlib
import re
import struct
import subprocess
import sys
import time

MIB = 1024 * 1024
SECTOR = 512
TABLE_BYTES = 34 * SECTOR
BACKUP_BYTES = 33 * SECTOR
DISK_NUMBER_RE = re.compile(r"^\\\\\.\\PhysicalDrive(\d+)$", re.IGNORECASE)
DEVICE_PATH_RE = re.compile(r"^\\\\[.?]\\")

if os.name == "nt":
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    DWORD_PTR = ctypes.POINTER(wintypes.DWORD)
    LONG64_PTR = ctypes.POINTER(ctypes.c_longlong)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                        LONG64_PTR, wintypes.DWORD]
    kernel.SetFilePointerEx.restype = wintypes.BOOL
    for transfer in (kernel.ReadFile, kernel.WriteFile):
        transfer.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                             DWORD_PTR, wintypes.LPVOID]
        transfer.restype = wintypes.BOOL
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                       DWORD_PTR, wintypes.LPVOID]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    for operation in (kernel.FlushFileBuffers, kernel.CloseHandle):
        operation.argtypes = [wintypes.HANDLE]
        operation.restype = wintypes.BOOL


def _image_stream(path):
    if DEVICE_PATH_RE.match(os.fspath(path)) or not os.path.isfile(path):
        raise SystemExit("dpflash: the image must be a regular file")
    if os.name != "nt":
        return open(path, "rb")
    # FILE_SHARE_READ denies writes and replacement until this handle closes.
    handle = _open_windows(os.fspath(path), write=False, share=1)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        close(handle)
        raise
    return os.fdopen(fd, "rb")


def _windows_disk(number):
    cmd = (f"$ErrorActionPreference='Stop'; Get-Disk -Number {number} | "
           "Select-Object Number,Path,Size,SerialNumber,LogicalSectorSize,IsBoot,IsSystem,"
           "IsReadOnly,IsOffline,NumberOfPartitions,"
           "@{n='Bus';e={$_.BusType.ToString()}},"
           "@{n='Style';e={$_.PartitionStyle.ToString()}} | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
                             capture_output=True, text=True, check=True, timeout=30)
        disk = json.loads(out.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"dpflash: could not query PhysicalDrive{number}: {exc}") from exc
    if not isinstance(disk, dict) or disk.get("Number") != number or not disk.get("Size"):
        raise SystemExit(f"dpflash: invalid disk information for PhysicalDrive{number}")
    return disk


def target_size(path):
    """Return the regular file size or the Windows physical disk length."""
    if os.name == "nt":
        match = DISK_NUMBER_RE.fullmatch(os.fspath(path))
        if match:
            return _windows_disk(int(match.group(1)))["Size"]
    return os.path.getsize(path)


def _open_windows(path, write, share=3):
    access = 0x80000000 | (0x40000000 if write else 0)
    handle = kernel.CreateFileW(path, access, share, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(f"open {path} (win32={ctypes.get_last_error()})")
    return handle


def open_target(path, write):
    if os.name == "nt" and DEVICE_PATH_RE.match(os.fspath(path)):
        return _open_windows(os.fspath(path), write)
    return open(path, "r+b" if write else "rb")


def _seek(handle, offset, size, phase):
    moved = ctypes.c_longlong()
    if not kernel.SetFilePointerEx(handle, offset, ctypes.byref(moved), 0):
        raise OSError(f"{phase}: seek offset={offset} length={size} win32={ctypes.get_last_error()}")
    if moved.value != offset:
        raise OSError(f"{phase}: seek offset={offset} length={size} moved={moved.value}")


def write_at(handle, offset, data, phase="write"):
    size = len(data)
    if isinstance(handle, int):
        _seek(handle, offset, size, phase)
        written = wintypes.DWORD()
        if not kernel.WriteFile(handle, data, size, ctypes.byref(written), None):
            raise OSError(f"{phase}: write offset={offset} length={size} win32={ctypes.get_last_error()}")
        count = written.value
    else:
        handle.seek(offset)
        count = handle.write(data)
    if count != size:
        raise OSError(f"{phase}: short write offset={offset}, expected {size}, wrote {count}")


def read_at(handle, offset, size, phase="read"):
    if isinstance(handle, int):
        _seek(handle, offset, size, phase)
        buf = ctypes.create_string_buffer(size)
        got = wintypes.DWORD()
        if not kernel.ReadFile(handle, buf, size, ctypes.byref(got), None):
            raise OSError(f"{phase}: read offset={offset} length={size} win32={ctypes.get_last_error()}")
        data = buf.raw if got.value == size else buf[:got.value]
    else:
        handle.seek(offset)
        data = handle.read(size)
    if len(data) != size:
        raise OSError(f"{phase}: short read offset={offset}, expected {size}, read {len(data)}")
    return data


def flush(handle, phase="flush"):
    if isinstance(handle, int):
        if not kernel.FlushFileBuffers(handle):
            raise OSError(f"{phase}: flush win32={ctypes.get_last_error()}")
    else:
        handle.flush()
        os.fsync(handle.fileno())


def close(handle):
    if isinstance(handle, int):
        if not kernel.CloseHandle(handle):
            raise OSError(f"close: win32={ctypes.get_last_error()}")
    else:
        handle.close()


def _device_ioctl(handle, code, size):
    buf = ctypes.create_string_buffer(size)
    got = wintypes.DWORD()
    if not kernel.DeviceIoControl(handle, code, None, 0, buf, size,
                                   ctypes.byref(got), None):
        raise OSError(f"prepare: ioctl={code:#x} win32={ctypes.get_last_error()}")
    if got.value < 8:
        raise OSError(f"prepare: short response for ioctl={code:#x}")
    return buf.raw[:got.value]


def _refresh_windows_disk(path):
    handle = _open_windows(path, write=False)
    try:
        returned = wintypes.DWORD()
        code = 0x00070140  # IOCTL_DISK_UPDATE_PROPERTIES
        if not kernel.DeviceIoControl(handle, code, None, 0, None, 0,
                                     ctypes.byref(returned), None):
            raise OSError(f"refresh partition cache: win32={ctypes.get_last_error()}")
    finally:
        close(handle)


def _require_blank_disk(handle, disk_size):
    length = _device_ioctl(handle, 0x7405C, 8)  # IOCTL_DISK_GET_LENGTH_INFO
    if struct.unpack_from("<Q", length)[0] != disk_size:
        raise OSError("prepare: raw handle capacity differs from the selected disk")
    layout = _device_ioctl(handle, 0x70050, 4096)  # IOCTL_DISK_GET_DRIVE_LAYOUT_EX
    style, count = struct.unpack_from("<II", layout)
    if count == 0 and style in (0, 1, 2):
        return
    # Windows may enumerate the four empty MBR slots after Clear-Disk.
    # DRIVE_LAYOUT_INFORMATION_EX places the 144-byte entries at offset 48.
    entries = range(48, 48 + 4 * 144, 144)
    if (style == 0 and count == 4 and len(layout) >= 48 + 4 * 144
            and all(not any(layout[off:off + 28]) and layout[off + 32] == 0
                    for off in entries)):
        mbr = read_at(handle, 0, SECTOR, "prepare MBR")
        if not any(mbr[446:510]):
            return
    raise OSError(f"prepare: expected a blank raw disk, layout={style} partitions={count}")


def _hash_range(handle, offset, size, prefix=b"", suffix=b"", phase="hash"):
    digest = hashlib.sha256(prefix)
    while offset < size:
        block = read_at(handle, offset, min(8 * MIB, size - offset), phase)
        digest.update(block)
        offset += len(block)
    digest.update(suffix)
    return digest.hexdigest()


def hash_target(target_path, size):
    """Return the SHA-256 of the first `size` bytes of the target."""
    handle = open_target(target_path, write=False)
    try:
        return _hash_range(handle, 0, size)
    finally:
        close(handle)


def _clear_tables(handle, disk_size, raw):
    areas = [(0, bytes(TABLE_BYTES))]
    if raw:
        areas.append((disk_size - BACKUP_BYTES, bytes(BACKUP_BYTES)))
    for offset, data in areas:
        write_at(handle, offset, data, "clear GPT")
    flush(handle, "clear GPT")
    for offset, data in areas:
        if read_at(handle, offset, len(data), "clear GPT") != data:
            raise OSError(f"clear GPT: read-back mismatch offset={offset} length={len(data)}")
    if raw:
        _require_blank_disk(handle, disk_size)


def _checked_disk(number, disk_path, disk_size, disk_serial):
    disk = _windows_disk(number)
    path = disk.get("Path") or ""
    if (not DEVICE_PATH_RE.match(path) or path.casefold() != disk_path.casefold()
            or disk["Size"] != disk_size
            or (disk_serial and (disk.get("SerialNumber") or "").strip() != disk_serial)
            or disk.get("Bus") not in ("USB", "SD", "MMC") or disk.get("IsBoot") is not False
            or disk.get("IsSystem") is not False or disk.get("IsReadOnly") is not False
            or disk.get("IsOffline") is not False or disk.get("LogicalSectorSize") != SECTOR):
        raise SystemExit("dpflash: disk identity or sector size changed before opening")
    if disk.get("Style") not in ("RAW", "MBR", "GPT") or disk.get("NumberOfPartitions") != 0:
        raise SystemExit("dpflash: Windows still reports a partition layout on the disk")
    return path


def flash(image_path, target_path, dry_run=False, defer_table=True, expected_sha=None,
          resume=False, verify=False, expand=False, disk_path=None, disk_size=None,
          disk_serial=None):
    chunk_kib = os.environ.get("DEEPOS_CHUNK_KIB") or "1024"
    if chunk_kib not in ("128", "256", "512", "1024"):
        raise SystemExit("dpflash: DEEPOS_CHUNK_KIB must be 128, 256, 512 or 1024")
    chunk_size = int(chunk_kib) * 1024
    throttle_ms = float(os.environ.get("DEEPOS_THROTTLE_MS") or "0")
    if not math.isfinite(throttle_ms) or throttle_ms < 0:
        raise SystemExit("dpflash: DEEPOS_THROTTLE_MS must be a finite, nonnegative number")
    path = os.fspath(target_path)
    raw = os.name == "nt" and DISK_NUMBER_RE.fullmatch(path)
    if not raw and not os.path.isfile(path):
        raise SystemExit("dpflash: target must be an existing regular file or Windows physical disk")
    if not raw and os.path.samefile(image_path, target_path):
        raise SystemExit("dpflash: the image and target must be different files")
    if raw and not dry_run:
        if not disk_path or not disk_size or not expected_sha:
            raise SystemExit("dpflash: use flash-deepos.ps1 to prepare and identify the Windows disk")
        if expand or not defer_table:
            raise SystemExit("dpflash: raw Windows flashing requires deferred GPT and no expansion")
        verify = True

    with _image_stream(image_path) as src:
        image_size = os.fstat(src.fileno()).st_size
        card_size = disk_size if raw and disk_size else target_size(path)
        if card_size < image_size:
            raise SystemExit(f"dpflash: target is {card_size} B, image needs {image_size} B")
        if image_size < TABLE_BYTES + BACKUP_BYTES:
            raise SystemExit("dpflash: image is too small for both GPT copies")
        if raw and (image_size % SECTOR or card_size % SECTOR):
            raise SystemExit("dpflash: image and card sizes must be multiples of 512 bytes")

        digest = _hash_range(src, 0, image_size, phase="hash image")
        print(f"image   {image_path} ({image_size} B)")
        print(f"target  {target_path} ({card_size} B)")
        print(f"sha256  {digest}")
        if expected_sha and digest != expected_sha.lower():
            raise SystemExit("dpflash: image sha256 does not match --expect-sha256")
        if dry_run:
            print("dry-run: nothing written")
            return 0

        table = read_at(src, 0, TABLE_BYTES) if defer_table else b""
        tail_offset = image_size - BACKUP_BYTES if defer_table else image_size
        tail = read_at(src, tail_offset, BACKUP_BYTES) if defer_table else b""
        disk_table = table
        tails = [(tail_offset, tail)] if defer_table else []
        relocate = raw and card_size > image_size
        if relocate:
            from expand_gpt import relocated_metadata
            disk_table, disk_tail = relocated_metadata(table, image_size, card_size)
            disk_tail_offset = card_size - len(disk_tail)
            # Clear any original backup sectors outside the relocated GPT region.
            stale_size = min(image_size, disk_tail_offset) - tail_offset
            tails = [(tail_offset, bytes(stale_size)), (disk_tail_offset, disk_tail)]
            print(f"GPT: relocating backup to byte {disk_tail_offset}; partition sizes preserved")
        if raw:
            path = _checked_disk(int(raw.group(1)), disk_path, card_size, disk_serial)
        handle = open_target(path, write=True)
        try:
            if raw:
                _require_blank_disk(handle, card_size)
            if defer_table:
                print("preparing: clearing old partition table locations")
                _clear_tables(handle, card_size, raw)
            offset = len(table)
            skipped = 0
            last_percent = -1
            while offset < tail_offset:
                # Align chunk boundaries to MiB so a transfer never straddles BOOT.
                size = min(chunk_size - offset % chunk_size, tail_offset - offset)
                chunk = read_at(src, offset, size, "read image")
                if resume and read_at(handle, offset, size, "resume") == chunk:
                    skipped += size
                else:
                    write_at(handle, offset, chunk, "payload")
                    if throttle_ms:
                        time.sleep(throttle_ms / 1000)
                offset += size
                percent = offset * 100 // image_size
                if percent != last_percent:
                    print(f"  payload {percent}% (skipped {skipped // MIB} MiB)", flush=True)
                    last_percent = percent
            if skipped:
                print(f"resume: {skipped // MIB} MiB were already correct, "
                      f"rewritten {(tail_offset - len(table) - skipped) // MIB} MiB")
            for offset, data in tails:
                write_at(handle, offset, data, "publish backup GPT")
            flush(handle, "payload and backup GPT")
            if verify:
                print("verifying the written range before publishing the primary GPT", flush=True)
                got = _hash_range(handle, len(table), tail_offset, table, tail, "verify payload")
                if got != digest:
                    raise OSError(f"verify payload: card sha256 mismatch ({got})")
            if defer_table:
                for offset, data in tails:
                    if read_at(handle, offset, len(data), "verify backup GPT") != data:
                        raise OSError(f"verify backup GPT: read-back mismatch at offset {offset}")
                write_at(handle, 0, disk_table, "publish primary GPT")
                flush(handle, "publish primary GPT")
                if read_at(handle, 0, len(disk_table), "verify primary GPT") != disk_table:
                    raise OSError("verify primary GPT: read-back mismatch")
                print("verified: partition tables read back byte-identical")
            if relocate:
                print("verified: image payload matches and the relocated GPT is intact")
            elif verify:
                print("verified: whole card matches the image")
        finally:
            close(handle)
    if raw:
        try:
            _refresh_windows_disk(path)
        except OSError as exc:
            print(f"warning: {exc}. Reconnect the card reader to refresh Windows.",
                  file=sys.stderr)
    if expand:
        import expand_gpt
        expand_gpt.expand_target(target_path, card_size)
    print("done: image written")
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
    parser.add_argument("--resume", action="store_true",
                        help="skip chunks that already match the image (retry after a reader hiccup)")
    parser.add_argument("--expand", action="store_true",
                        help="relocate backup GPT on a larger test file and preserve partition sizes")
    parser.add_argument("--verify", action="store_true",
                        help="after writing, read the whole card back and compare sha256")
    parser.add_argument("--disk-path", help=argparse.SUPPRESS)
    parser.add_argument("--disk-size", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--disk-serial", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.list:
        return list_disks()
    if not args.image or not args.target:
        parser.error("--image and --target are required unless --list is used")
    try:
        return flash(args.image, args.target, dry_run=args.dry_run,
                     defer_table=not args.no_defer_table, expected_sha=args.expect_sha256,
                     resume=args.resume, verify=args.verify, expand=args.expand,
                     disk_path=args.disk_path, disk_size=args.disk_size, disk_serial=args.disk_serial)
    except (OSError, ValueError) as exc:
        print(f"dpflash: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
