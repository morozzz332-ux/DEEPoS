#!/usr/bin/env python3
"""The card is bigger than the image: after flashing, the GPT must cover it."""
import binascii
import pathlib
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path("/w")
MKIMAGE = ROOT / "tools/mkimage.py"
DPFLASH = ROOT / "tools/dpflash.py"
EXPAND = ROOT / "tools/expand_gpt.py"
SECTOR = 512
GIB = 1024 ** 3
MIB = 1024 ** 2

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def gpt_state(path: pathlib.Path):
    with open(path, "rb") as f:
        f.seek(SECTOR)
        header = f.read(SECTOR)
        sig = header[:8]
        entries_lba, = struct.unpack_from("<Q", header, 72)
        entries_crc, = struct.unpack_from("<I", header, 88)
        backup_lba, = struct.unpack_from("<Q", header, 32)
        last_usable, = struct.unpack_from("<Q", header, 48)
        f.seek(entries_lba * SECTOR)
        entries = f.read(32 * 128)
        actual_crc = binascii.crc32(entries) & 0xFFFFFFFF
        parts = []
        for i in range(32):
            first, last = struct.unpack_from("<QQ", entries, i * 128 + 32)
            if first and last:
                parts.append((first, last))
    return {
        "sig": sig,
        "entries_crc_ok": entries_crc == actual_crc,
        "backup_lba": backup_lba,
        "last_usable": last_usable,
        "parts": parts,
    }


def build_image(tmp: pathlib.Path, size_mib: int) -> pathlib.Path:
    layout = ROOT / "tests/fixtures/layout-small.json"
    boot = tmp / "boot"
    boot.mkdir()
    (boot / "KERNEL").write_bytes(b"k" * 4096)
    sys_a = tmp / "a.squashfs"
    sys_a.write_bytes(b"hsqs" + b"\x00" * 4092)
    data = tmp / "data"
    data.mkdir()
    out = tmp / "card.img"
    proc = subprocess.run([sys.executable, str(MKIMAGE), "--out", str(out),
                           "--size-mib", str(size_mib), "--layout", str(layout),
                           "--boot", str(boot), "--sys-a", str(sys_a),
                           "--data", str(data)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr[-500:])
    return out


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="deepos-expand-"))
    image = build_image(tmp, 129)
    before = gpt_state(image)
    check("image has GPT", before["sig"] == b"EFI PART")
    check("image GPT CRCs are valid", before["entries_crc_ok"])

    card = tmp / "card-512m.img"
    card.write_bytes(b"\x00" * (512 * MIB))
    proc = subprocess.run([sys.executable, str(DPFLASH), "--image", str(image),
                           "--target", str(card), "--expand"],
                          capture_output=True, text=True, timeout=300)
    check("dpflash --expand exits 0", proc.returncode == 0, proc.stderr[-300:])
    check("expand reported in the log", "expand:" in proc.stdout, proc.stdout[-300:])

    after = gpt_state(card)
    card_sectors = card.stat().st_size // SECTOR
    check("backup header moved to the card end", after["backup_lba"] == card_sectors - 1,
          f'{after["backup_lba"]} vs {card_sectors - 1}')
    check("entries CRC still valid after expand", after["entries_crc_ok"])
    check("last partition now ends at last_usable",
          after["parts"][-1][1] == after["last_usable"],
          f'{after["parts"][-1][1]} vs {after["last_usable"]}')
    check("last partition starts where the image put it",
          after["parts"][-1][0] == before["parts"][-1][0])
    check("other partitions untouched", after["parts"][:-1] == before["parts"][:-1])

    header_at_end = card.read_bytes()[card_sectors * SECTOR - SECTOR:][:8]
    check("backup GPT signature is at the card end", header_at_end == b"EFI PART")

    empty = tmp / "card-empty.img"
    empty.write_bytes(b"\x00" * (64 * MIB))
    proc = subprocess.run([sys.executable, str(EXPAND), "--target", str(empty)],
                          capture_output=True, text=True)
    check("expand refuses a card without GPT", proc.returncode != 0)

    print()
    if failures:
        print(f"FAIL  expand: {len(failures)} check(s) failed")
        return 1
    print("PASS  expand: GPT grows to the card size with valid CRCs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
