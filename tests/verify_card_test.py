#!/usr/bin/env python3
"""Checks verify-card.py against a flashed image and a damaged one."""
import pathlib
import struct
import subprocess
import sys
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
SECTOR = 512
MIB = 1024 ** 2


def run(args, expect=0):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if expect is not None and proc.returncode != expect:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"{args[0]} exited {proc.returncode}, expected {expect}")
    return proc.stdout + proc.stderr


def build_image(work, size_mib=128):
    boot = work / "boot"
    (boot / "extlinux").mkdir(parents=True)
    (boot / "extlinux/extlinux.conf").write_text(
        "LABEL DEEPoS\nLINUX /KERNEL\nFDT /dtbs/rk3326-r36s-v20.dtb\n")
    (boot / "KERNEL").write_bytes(b"\x01" * (1024 * 1024))
    (boot / "dtbs").mkdir()
    (boot / "dtbs/rk3326-r36s-v20.dtb").write_bytes(b"\xd0\x0d\xfe\xed" + bytes(2048))
    sysfs = work / "sys"
    sysfs.mkdir()
    data = work / "data"
    data.mkdir()
    (data / "user-settings").write_bytes(b"saved settings")
    image = work / "card.img"
    run([PY, "tools/mkimage.py", "--layout", str(ROOT / "tests/fixtures/layout-small.json"),
         "--size-mib", str(size_mib),
         "--out", str(image), "--boot", str(boot), "--sys-a", str(sysfs),
         "--sys-b", str(sysfs), "--data", str(data)])
    return image


def flash(image, target, size):
    with target.open("wb") as handle:
        handle.truncate(size)
    run([PY, "tools/dpflash.py", "--image", str(image), "--target", str(target),
         "--verify"])
    return target


def set_header_field(header, fmt, offset, value):
    raw = bytearray(header)
    struct.pack_into(fmt, raw, offset, value)
    struct.pack_into("<I", raw, 16, 0)
    size = struct.unpack_from("<I", raw, 12)[0]
    struct.pack_into("<I", raw, 16, zlib.crc32(raw[:size]))
    return raw


def check_card(work):
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            failures.append(name)

    image = build_image(work)
    image_size = image.stat().st_size
    target = flash(image, work / "target.img", image_size)
    verify = [PY, "tools/verify-card.py", "--target", str(target)]

    out = run(verify)
    check("clean card passes", "PASS  card:" in out, out.strip().splitlines()[-1:])

    with open(target, "r+b") as handle:
        handle.seek(SECTOR)
        primary = handle.read(SECTOR)
        backup_offset = struct.unpack_from("<Q", primary, 32)[0] * SECTOR
        handle.seek(backup_offset)
        backup = handle.read(SECTOR)
        primary_entries = struct.unpack_from("<Q", primary, 72)[0] * SECTOR
        backup_entries = struct.unpack_from("<Q", backup, 72)[0] * SECTOR
        handle.seek(primary_entries + 4 * 128 + 32)
        roms = struct.unpack("<Q", handle.read(8))[0] * SECTOR
        handle.seek(primary_entries + 40)
        damaged_entry = bytes([handle.read(1)[0] ^ 1])

        for name, offset, replacement, error in [
            ("protective MBR span", 458, bytes(4), "protective MBR"),
            ("primary entry array CRC", primary_entries + 40, damaged_entry, "primary partition entries CRC"),
            ("backup entry array CRC", backup_entries + 40, damaged_entry, "backup partition entries CRC"),
            ("backup header CRC", backup_offset + 16, bytes(4), "backup GPT header CRC"),
            ("backup header location", backup_offset, set_header_field(backup, "<Q", 24, 1),
             "backup GPT header LBA"),
            ("backup alternate LBA", backup_offset, set_header_field(backup, "<Q", 32, 2),
             "backup GPT alternate LBA"),
            ("exFAT declared size vs partition", roms + 72, struct.pack("<Q", 1024), "ROMS exFAT volume length"),
        ]:
            handle.seek(offset)
            original = handle.read(len(replacement))
            handle.seek(offset)
            handle.write(replacement)
            handle.flush()
            out = run(verify, expect=1)
            check(f"rejects damaged {name}", "FAIL  card:" in out and error in out, out)
            handle.seek(offset)
            handle.write(original)

        count, width = struct.unpack_from("<II", primary, 80)
        handle.seek(primary_entries)
        original = handle.read(count * width)
        entries = bytearray(original)
        last_usable = struct.unpack_from("<Q", primary, 48)[0]
        struct.pack_into("<Q", entries, 4 * width + 40, last_usable + 1)
        new_crc = zlib.crc32(entries)
        for header_offset, header, entries_offset in [
            (SECTOR, primary, primary_entries),
            (backup_offset, backup, backup_entries),
        ]:
            handle.seek(header_offset)
            handle.write(set_header_field(header, "<I", 88, new_crc))
            handle.seek(entries_offset)
            handle.write(entries)
        handle.flush()
        out = run(verify, expect=1)
        check("rejects partition outside usable range with matching CRCs",
              "partition 5 lies outside the GPT usable range" in out, out)

    target = flash(image, target, image_size + 4 * MIB)
    with_image = verify + ["--image", str(image)]
    out = run(with_image)
    check("unexpanded image prefix on a larger card passes",
          "PASS  card:" in out and "card prefix matches the image" in out, out)

    with target.open("r+b") as handle:
        handle.seek(768 * 1024)
        handle.write(b"\xff" * 8)
    out = run(with_image, expect=1)
    check("--image catches a stray write", "card prefix SHA-256 mismatch" in out, out)

    with target.open("r+b") as handle:
        handle.seek(-SECTOR, 2)
        handle.write(backup)
    out = run(verify, expect=1)
    check("unexpanded card rejects a conflicting header at the device end",
          "conflicting GPT header at the physical device end" in out, out)

    print()
    if failures:
        print(f"FAIL  verify-card: {len(failures)} check(s) failed")
        return 1
    print("PASS  verify-card: clean card, damaged CRC, image prefix")
    return 0


def main():
    with tempfile.TemporaryDirectory(prefix="verifycard-") as directory:
        return check_card(pathlib.Path(directory))


if __name__ == "__main__":
    sys.exit(main())
