#!/usr/bin/env python3
"""Verify a DEEPoS card image end to end, before it is written to a card.

Checks (all offline, no root, no mounted partitions):
  * GPT: protective MBR, primary/backup headers, CRC32 of header and entries,
    agreement between primary and backup copies;
  * partitions: names, alignment, no overlaps, image big enough;
  * filesystem signatures and labels (FAT32 / squashfs / ext4 / exFAT);
  * Rockchip boot chain: idbloader.img at 32 KiB, u-boot.itb at 8 MiB
    (byte-for-byte against build/uboot when it exists);
  * BOOT payload: MANIFEST.json inside FAT, KERNEL/dtb sizes and sha256;
  * squashfs payload: required binaries and init files present.

Usage:
    python3 tools/verify-image.py build/deepos-r36s-v20.img
    python3 tools/verify-image.py --json build/deepos-r36s-v20.img
    python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import os
import subprocess
import sys
import tempfile
import zlib

from loader_donor import START as DONOR_START, donor_region
from mkboot import BOOT_SCRIPT, sha256_file, valid_boot_script, validate_extlinux

SECTOR = 512
GPT_SIG = b"EFI PART"
CRC_OFFSET = 16
ENTRY_SIZE = 128
LOADER_OFFSETS = {"idbloader.img": 32 * 1024, "u-boot.itb": 8 * 1024 * 1024}
FAT32_TYPE_OFFSET = 82
EXT4_MAGIC_OFFSET = 1080
EXFAT_OEM_OFFSET = 3

# Files that must exist inside the squashfs root.
REQUIRED_ROOTFS = [
    "sbin/init",
    "bin/busybox",
    "usr/bin/launcher",
    "usr/bin/modd",
    "usr/bin/saved",
    "usr/bin/updatr",
    "etc/os-release",
    "etc/inittab",
    "etc/init.d/rcS",
]


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.ok: list[str] = []
        self.facts: dict[str, object] = {}

    def check(self, name: str, cond: bool, extra: str = "") -> bool:
        if cond:
            self.ok.append(name)
        else:
            self.failures.append(f"{name}{(' вЂ” ' + extra) if extra else ''}")
        return cond

    def info(self, key: str, value: object) -> None:
        self.facts[key] = value


def read_at(fh, offset: int, size: int) -> bytes:
    fh.seek(offset)
    return fh.read(size)


def parse_gpt_header(raw: bytes) -> dict:
    if len(raw) < 92 or raw[:8] != GPT_SIG:
        return {}
    (revision, header_size, header_crc, _reserved, current_lba, backup_lba,
     first_usable, last_usable) = struct.unpack_from("<IIIIQQQQ", raw, 8)
    entries_lba, num_entries, entry_size, entries_crc = struct.unpack_from("<QIII", raw, 72)
    disk_guid = raw[56:72]
    crc_ok = False
    if 92 <= header_size <= len(raw):
        muted = bytearray(raw[:header_size])
        muted[CRC_OFFSET:CRC_OFFSET + 4] = b"\0\0\0\0"
        crc_ok = zlib.crc32(bytes(muted)) & 0xFFFFFFFF == header_crc
    return {
        "revision": revision,
        "header_size": header_size,
        "current_lba": current_lba,
        "backup_lba": backup_lba,
        "first_usable": first_usable,
        "last_usable": last_usable,
        "entries_lba": entries_lba,
        "num_entries": num_entries,
        "entry_size": entry_size,
        "entries_crc": entries_crc,
        "disk_guid": disk_guid.hex(),
        "crc_ok": crc_ok,
    }


def parse_entries(raw: bytes, count: int) -> list[dict]:
    parts = []
    for i in range(count):
        entry = raw[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
        if len(entry) < ENTRY_SIZE or entry[:16] == b"\0" * 16:
            continue
        first_lba, last_lba, attrs = struct.unpack_from("<QQQ", entry, 32)
        name = entry[56:128].decode("utf-16-le", "ignore").rstrip("\0")
        parts.append({
            "index": i + 1,
            "name": name,
            "first_lba": first_lba,
            "last_lba": last_lba,
            "disk_guid": entry[16:32].hex(),
            "attrs": attrs,
        })
    return parts


def crc_entries(raw: bytes, count: int, entry_size: int) -> int:
    return zlib.crc32(raw[:count * entry_size]) & 0xFFFFFFFF


def check_gpt(fh, image_size: int, rep: Report) -> list[dict]:
    mbr = read_at(fh, 0, SECTOR)
    rep.check("protective MBR signature", mbr[510:512] == b"\x55\xaa", mbr[510:512].hex())
    ptype = mbr[446 + 4]
    rep.check("protective MBR partition type 0xEE", ptype == 0xEE, f"0x{ptype:02x}")

    primary = parse_gpt_header(read_at(fh, SECTOR, SECTOR))
    rep.check("GPT primary header present", bool(primary))
    if not primary:
        return []
    rep.check("GPT primary header CRC", primary["crc_ok"])

    last_lba = image_size // SECTOR - 1
    count, width = primary["num_entries"], primary["entry_size"]
    table_sectors = (count * width + SECTOR - 1) // SECTOR
    if not rep.check("GPT entry geometry", primary["entries_lba"] == 2
                     and 1 <= count <= 4096 and width == ENTRY_SIZE
                     and table_sectors < last_lba // 2):
        return []
    rep.check("GPT primary points at image end",
              primary["current_lba"] == 1 and primary["backup_lba"] == last_lba)
    rep.check("GPT usable LBA bounds", 2 + table_sectors <= primary["first_usable"]
              <= primary["last_usable"] < last_lba - table_sectors)
    entries_raw = read_at(fh, 2 * SECTOR, count * width)
    rep.check("GPT entries array length", len(entries_raw) == count * width)
    rep.check("GPT entries CRC", crc_entries(entries_raw, count, width)
              == primary["entries_crc"])

    backup = parse_gpt_header(read_at(fh, image_size - SECTOR, SECTOR))
    if rep.check("GPT backup header present", bool(backup)):
        rep.check("GPT backup header CRC", backup["crc_ok"])
        rep.check("GPT backup points at primary", backup["current_lba"] == last_lba
                  and backup["backup_lba"] == 1)
        rep.check("GPT backup metadata matches primary", all(
            backup[k] == primary[k] for k in ("disk_guid", "num_entries", "entry_size",
                                              "first_usable", "last_usable", "entries_crc")))
        backup_entries_lba = last_lba - table_sectors
        rep.check("GPT backup entries LBA", backup["entries_lba"] == backup_entries_lba)
        rep.check("GPT backup entries match primary",
                  read_at(fh, backup_entries_lba * SECTOR, count * width) == entries_raw)

    parts = parse_entries(entries_raw, primary["num_entries"])
    rep.info("partitions", parts)
    rep.check("partition count is 5", len(parts) == 5, str(len(parts)))
    rep.check("partitions aligned to 1 MiB",
              all(p["first_lba"] * SECTOR % (1024 * 1024) == 0 for p in parts))
    ordered = sorted(parts, key=lambda p: p["first_lba"])
    overlap = any(ordered[i]["last_lba"] >= ordered[i + 1]["first_lba"] for i in range(len(ordered) - 1))
    rep.check("partitions do not overlap", not overlap)
    rep.check("all partitions are within usable GPT LBAs", all(
        primary["first_usable"] <= p["first_lba"] <= p["last_lba"] <= primary["last_usable"]
        for p in parts))
    return parts


def check_signatures(fh, parts: list[dict], rep: Report) -> None:
    by_name = {p["name"]: p for p in parts}
    payloads = {
        "BOOT": ("fat", FAT32_TYPE_OFFSET, b"FAT32"),
        "DEEPOS_A": ("squashfs", 0, b"hsqs"),
        "DEEPOS_B": ("squashfs", 0, b"hsqs"),
        "DATA": ("ext4", EXT4_MAGIC_OFFSET, b"\x53\xef"),
        "ROMS": ("exfat", EXFAT_OEM_OFFSET, b"EXFAT   "),
    }
    for name, (kind, offset, magic) in payloads.items():
        part = by_name.get(name)
        if not rep.check(f"partition {name} exists", part is not None):
            continue
        data = read_at(fh, part["first_lba"] * SECTOR + offset, len(magic))
        rep.check(f"{name} looks like {kind}", data == magic, f"got {data!r}")


def check_loader(fh, loader_dir: pathlib.Path, rep: Report) -> None:
    for name, offset in LOADER_OFFSETS.items():
        src = loader_dir / name
        if not rep.check(f"loader {name} available", src.is_file(), str(src)):
            continue
        blob = src.read_bytes()
        got = read_at(fh, offset, len(blob))
        rep.check(f"{name} placed at {offset // 1024} KiB", got == blob,
                  f"{len(got)} of {len(blob)} bytes match")


def extract_boot_member(fh, part, member, *, digest=False):
    offset = part["first_lba"] * SECTOR
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "member.bin"
        try:
            proc = subprocess.run(
                ["mcopy", "-n", "-i", f"{fh.name}@@{offset}", f"::{member}", str(out)],
                capture_output=True, env=dict(os.environ, MTOOLS_SKIP_CHECK="1"),
            )
        except FileNotFoundError:
            return None
        if proc.returncode != 0 or not out.is_file():
            return None
        return sha256_file(out) if digest else out.read_bytes()


def check_boot_payload(fh, parts, rep, *, require_script=False):
    boot = next((p for p in parts if p["name"] == "BOOT"), None)
    if not rep.check("BOOT partition present for payload check", boot is not None):
        return
    manifest_blob = extract_boot_member(fh, boot, "MANIFEST.json")
    try:
        manifest = json.loads(manifest_blob or b"")
        hashes = manifest["files"]
        if not isinstance(hashes, dict):
            raise ValueError("files must be an object")
    except (ValueError, KeyError, TypeError) as exc:
        rep.check("BOOT MANIFEST.json parses", False, str(exc))
        return

    rep.info("manifest", {"version": manifest.get("version"), "board": manifest.get("board"),
                          "files": len(hashes)})
    for member in ("KERNEL", "dtbs/rk3326-r36s-v20.dtb"):
        actual = extract_boot_member(fh, boot, member, digest=True)
        rep.check(f"BOOT {member} sha256 matches manifest",
                  actual is not None and actual == hashes.get(member))

    name = "extlinux/extlinux.conf"
    config = extract_boot_member(fh, boot, name)
    if rep.check(f"BOOT contains {name}", config is not None):
        try:
            validate_extlinux(config.decode("utf-8"))
        except ValueError as exc:
            rep.check("BOOT extlinux kernel arguments", False, str(exc))
        else:
            rep.check("BOOT extlinux kernel arguments", True)
        rep.check("BOOT extlinux sha256 matches manifest",
                  hashlib.sha256(config).hexdigest() == hashes.get(name))

    if require_script or BOOT_SCRIPT in hashes:
        script = extract_boot_member(fh, boot, BOOT_SCRIPT)
        if rep.check("BOOT contains a valid boot.scr",
                     script is not None and valid_boot_script(script)):
            rep.check("BOOT boot.scr sha256 matches manifest",
                      hashlib.sha256(script).hexdigest() == hashes.get(BOOT_SCRIPT))


def check_squashfs(fh, parts: list[dict], rep: Report) -> None:
    part = next((p for p in parts if p["name"] == "DEEPOS_A"), None)
    if not rep.check("DEEPOS_A partition present", part is not None):
        return
    offset = part["first_lba"] * SECTOR
    size = (part["last_lba"] - part["first_lba"] + 1) * SECTOR
    listing = ""
    try:
        proc = subprocess.run(
            ["unsquashfs", "-o", str(offset), "-l", fh.name],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            listing = proc.stdout
    except FileNotFoundError:
        proc = None
    if not listing:
        # Fallback: unsquashfs is optional; names of uncompressed entries still
        # live in the inode area, so scan the whole partition.
        chunk = 8 * 1024 * 1024
        pos = 0
        parts_text = []
        while pos < size:
            parts_text.append(read_at(fh, offset + pos, min(chunk, size - pos)).decode("latin-1"))
            pos += chunk
        listing = "".join(parts_text)
    missing = [name for name in REQUIRED_ROOTFS if name not in listing]
    rep.check("squashfs has required files", not missing, ", ".join(missing[:4]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify a DEEPoS image before flashing")
    ap.add_argument("image", type=pathlib.Path)
    loader = ap.add_mutually_exclusive_group()
    loader.add_argument("--loader", type=pathlib.Path, default=pathlib.Path("build/uboot"))
    loader.add_argument("--loader-donor", type=pathlib.Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-rootfs", action="store_true")
    args = ap.parse_args()

    rep = Report()
    if not rep.check("image exists", args.image.is_file(), str(args.image)):
        return 1
    size = args.image.stat().st_size
    rep.info("image", {"path": str(args.image), "size": size,
                       "sha256": sha256_file(args.image)})

    with args.image.open("rb") as fh:
        parts = check_gpt(fh, size, rep)
        if parts:
            check_signatures(fh, parts, rep)
            if args.loader_donor:
                try:
                    blob = donor_region(args.loader_donor)
                except (OSError, ValueError) as exc:
                    rep.check("Rockchip donor loader readable", False, str(exc))
                else:
                    rep.check("Rockchip loader matches donor",
                              read_at(fh, DONOR_START, len(blob)) == blob)
            else:
                check_loader(fh, args.loader, rep)
            check_boot_payload(fh, parts, rep, require_script=bool(args.loader_donor))
            if not args.skip_rootfs:
                check_squashfs(fh, parts, rep)
        else:
            rep.check("image has a usable GPT", False)

    if args.json:
        print(json.dumps({"ok": not rep.failures, "checks": rep.ok,
                          "failures": rep.failures, "facts": rep.facts},
                         ensure_ascii=False, indent=2, default=str))
    else:
        for name in rep.ok:
            print(f"  ok   {name}")
        for failure in rep.failures:
            print(f"  FAIL {failure}")
        print()
        if rep.failures:
            print(f"FAIL  verify-image: {len(rep.failures)} of {len(rep.ok) + len(rep.failures)} checks failed")
        else:
            print(f"PASS  verify-image: {len(rep.ok)} checks")
    return 1 if rep.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
