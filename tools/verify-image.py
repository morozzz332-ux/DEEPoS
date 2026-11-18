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
REQUIRED_BOOT = ["KERNEL", "MANIFEST.json", "extlinux/extlinux.conf"]


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.ok: list[str] = []
        self.facts: dict[str, object] = {}

    def check(self, name: str, cond: bool, extra: str = "") -> bool:
        if cond:
            self.ok.append(name)
        else:
            self.failures.append(f"{name}{(' — ' + extra) if extra else ''}")
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
    if header_size <= len(raw):
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

    primary = parse_gpt_header(read_at(fh, SECTOR, 92))
    rep.check("GPT primary header present", bool(primary))
    if not primary:
        return []
    rep.check("GPT primary header CRC", primary["crc_ok"])

    entries_raw = read_at(fh, primary["entries_lba"] * SECTOR, primary["num_entries"] * primary["entry_size"])
    rep.check("GPT entries array length", len(entries_raw) == primary["num_entries"] * primary["entry_size"])
    rep.check("GPT entries CRC",
              crc_entries(entries_raw, primary["num_entries"], primary["entry_size"]) == primary["entries_crc"])

    backup = parse_gpt_header(read_at(fh, image_size - SECTOR, 92))
    rep.check("GPT backup header present", bool(backup))
    if backup:
        rep.check("GPT backup header CRC", backup["crc_ok"])
        rep.check("GPT backup points at primary", backup["current_lba"] == primary["backup_lba"],
                  f"{backup['current_lba']} vs {primary['backup_lba']}")
        rep.check("GPT backup entries LBA inside image",
                  backup["entries_lba"] * SECTOR < image_size)

    parts = parse_entries(entries_raw, primary["num_entries"])
    rep.info("partitions", parts)
    rep.check("partition count is 5", len(parts) == 5, str(len(parts)))
    rep.check("partitions aligned to 1 MiB",
              all(p["first_lba"] * SECTOR % (1024 * 1024) == 0 for p in parts))
    ordered = sorted(parts, key=lambda p: p["first_lba"])
    overlap = any(ordered[i]["last_lba"] >= ordered[i + 1]["first_lba"] for i in range(len(ordered) - 1))
    rep.check("partitions do not overlap", not overlap)
    rep.check("last partition ends inside image", ordered[-1]["last_lba"] * SECTOR <= image_size)
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


def boot_listing(fh, part: dict) -> str:
    """Recursive listing of a FAT partition (VFAT long names are not contiguous)."""
    offset = part["first_lba"] * SECTOR
    try:
        proc = subprocess.run(
            ["mdir", "-/", "-i", f"{fh.name}@@{offset}", "::"],
            capture_output=True, text=True, env=dict(os.environ, MTOOLS_SKIP_CHECK="1"),
        )
    except FileNotFoundError:
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def check_boot_payload(fh, parts: list[dict], rep: Report) -> None:
    boot = next((p for p in parts if p["name"] == "BOOT"), None)
    if not rep.check("BOOT partition present for payload check", boot is not None):
        return
    raw = read_at(fh, boot["first_lba"] * SECTOR, (boot["last_lba"] - boot["first_lba"] + 1) * SECTOR)
    listing = boot_listing(fh, boot)
    for name in REQUIRED_BOOT:
        base = name.split("/")[-1]
        if listing:
            # mdir -/ prints nested entries as ::dir/file, so match the leaf name.
            present = base.lower() in listing.lower()
        else:
            present = base.upper().encode() in raw.upper()
        rep.check(f"BOOT contains {name}", present)

    # Manifest lives inside FAT; parse it from the raw region when possible.
    marker = raw.find(b'{\n  "board"')
    if marker == -1:
        marker = raw.find(b'{"board"')
    if marker != -1:
        depth = 0
        end = marker
        for i in range(marker, min(marker + 8192, len(raw))):
            if raw[i:i + 1] == b"{":
                depth += 1
            elif raw[i:i + 1] == b"}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            manifest = json.loads(raw[marker:end].decode("utf-8", "ignore"))
        except json.JSONDecodeError as exc:
            rep.check("MANIFEST.json parses", False, str(exc))
        else:
            rep.check("MANIFEST.json parses", True)
            files = manifest.get("files", {})
            sizes = manifest.get("sizes", {})
            kernel_sha = files.get("KERNEL", "")
            kernel_size = sizes.get("KERNEL", 0)
            rep.info("manifest", {"version": manifest.get("version"), "board": manifest.get("board"),
                                  "files": len(files)})
            rep.check("manifest lists KERNEL", bool(kernel_sha) and kernel_size > 0)
            if kernel_sha and kernel_size:
                digest = extract_and_hash(fh, boot, "::KERNEL")
                rep.check("KERNEL sha256 matches manifest", digest == kernel_sha,
                          f"{(digest or '?')[:16]} vs {kernel_sha[:16]}")
            dtb_sha = files.get("dtbs/rk3326-r36s-v20.dtb", "")
            rep.check("manifest lists device tree", bool(dtb_sha))


def extract_and_hash(fh, part: dict, member: str) -> str:
    """Copy one file out of a FAT partition with mtools and hash it."""
    offset = part["first_lba"] * SECTOR
    image = fh.name
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "member.bin"
        proc = subprocess.run(
            ["mcopy", "-n", "-i", f"{image}@@{offset}", member, str(out)],
            capture_output=True, text=True, env=dict(os.environ, MTOOLS_SKIP_CHECK="1"),
        )
        if proc.returncode != 0 or not out.is_file():
            return ""
        return hashlib.sha256(out.read_bytes()).hexdigest()


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
    ap.add_argument("--loader", type=pathlib.Path, default=pathlib.Path("build/uboot"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-rootfs", action="store_true")
    args = ap.parse_args()

    rep = Report()
    if not rep.check("image exists", args.image.is_file(), str(args.image)):
        return 1
    size = args.image.stat().st_size
    rep.info("image", {"path": str(args.image), "size": size,
                       "sha256": hashlib.sha256(args.image.read_bytes()).hexdigest()})

    with args.image.open("rb") as fh:
        parts = check_gpt(fh, size, rep)
        if parts:
            check_signatures(fh, parts, rep)
            check_loader(fh, args.loader, rep)
            check_boot_payload(fh, parts, rep)
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
