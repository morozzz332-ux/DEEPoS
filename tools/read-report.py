#!/usr/bin/env python3
r"""Pull the boot report off a DEEPoS card without drive letters.

Windows often refuses to mount the freshly written card (no letter, or the
volume cache still points at the old table), and the console writes its report
to `BOOT/report/`. This tool reads the raw device, finds the BOOT partition in
the GPT, extracts it to a temporary file and copies `report/` out of it with
mtools.

  python tools/read-report.py --target \\.\PhysicalDrive2 --out build/device-report

Exit code 0 - report copied (or BOOT has no report yet), 1 - card looks wrong.
"""
import argparse
import pathlib
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dpflash  # noqa: E402

SECTOR = 512
MIB = 1024 ** 2
ENTRY_SIZE = 128
ENTRY_COUNT = 32
REPORT_FILES = ["checks.txt", "boot.txt", "selftest.txt", "temps.txt",
                "mounts.txt", "free.txt", "cpufreq.txt", "modules.txt", "dmesg.txt"]


def read(handle, offset, size):
    return dpflash.read_at(handle, offset, size)


def decode_label(entry):
    raw = entry[56:128]
    try:
        text = raw.decode("utf-16-le").split("\x00", 1)[0]
        if text.isprintable():
            return text
    except UnicodeDecodeError:
        pass
    return raw.split(b"\x00", 1)[0].decode("utf-8", "replace")


def find_boot(handle):
    """Return (offset_bytes, size_bytes, label) of the BOOT partition."""
    header = read(handle, SECTOR, SECTOR)
    if header[:8] != b"EFI PART":
        raise SystemExit("read-report: no GPT header on this target")
    entries_lba = struct.unpack_from("<Q", header, 72)[0]
    count = struct.unpack_from("<I", header, 80)[0]
    size = struct.unpack_from("<I", header, 84)[0]
    count = min(count, ENTRY_COUNT)
    entries = read(handle, entries_lba * SECTOR, count * size)
    for index in range(count):
        raw = entries[index * size:(index + 1) * size]
        if not raw or raw[:16] == bytes(16):
            continue
        label = decode_label(raw)
        first, last = struct.unpack_from("<QQ", raw, 32)
        return first * SECTOR, (last - first + 1) * SECTOR, label
    raise SystemExit("read-report: no partitions in the GPT")


def extract(handle, offset, size, out):
    with open(out, "wb") as dst:
        done = 0
        while done < size:
            chunk = min(4 * MIB, size - done)
            dst.write(read(handle, offset + done, chunk))
            done += chunk


def mdir(image):
    result = subprocess.run(["mdir", "-/", "-i", str(image), "::report"],
                            capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the DEEPoS boot report from a card")
    parser.add_argument("--target", required=True,
                        help=r"raw device (\\.\PhysicalDrive2) or an image file")
    parser.add_argument("--out", default="build/device-report")
    parser.add_argument("--list", action="store_true", help="only list BOOT/report")
    args = parser.parse_args(argv)

    handle = dpflash.open_target(args.target, write=False)
    try:
        offset, size, label = find_boot(handle)
        print(f"BOOT: offset={offset // MIB} MiB size={size // MIB} MiB label={label}")
        with tempfile.TemporaryDirectory(prefix="deepos-report-") as tmp:
            boot = pathlib.Path(tmp) / "boot.img"
            if size > 512 * MIB:
                raise SystemExit(f"read-report: BOOT partition looks too big ({size} B)")
            extract(handle, offset, size, boot)
            ok, text = mdir(boot)
            if not ok:
                raise SystemExit("read-report: BOOT/report is missing (nothing has booted yet)")
            print(text.strip())
            if args.list:
                return 0
            out = pathlib.Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            for name in REPORT_FILES:
                subprocess.run(["mcopy", "-n", "-i", str(boot), f"::report/{name}", str(out / name)],
                               capture_output=True, text=True)
            print(f"copied to {out}")
            checks = out / "checks.txt"
            if checks.exists():
                print("--- checks.txt ---")
                print(checks.read_text(encoding="utf-8", errors="replace").strip())
    finally:
        dpflash.close(handle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
