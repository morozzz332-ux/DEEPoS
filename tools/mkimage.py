#!/usr/bin/env python3
"""DEEPoS image builder.

Builds a GPT disk image for the R36S-V20 card layout:

    BOOT    fat32     256 MiB  kernel, dtbs, overlays, splash
    SYS_A   squashfs  700 MiB  rootfs A
    SYS_B   squashfs  700 MiB  rootfs B (A/B updates)
    DATA    ext4     1536 MiB  configs, saves, modules
    ROMS    exfat     rest     ROMs, visible to a PC

Everything is deterministic: partition GUIDs are derived from the image name
and the partition name, so two builds of the same inputs are byte identical.
That is what makes golden tests possible without a device.

Filesystem creation is delegated to the standard tools (mkfs.vfat + mcopy,
mksquashfs, mkfs.ext4, mkfs.exfat); `make image` runs them inside the build
container. Sizes can be overridden with --size-mib for small test images.
"""
import argparse
import glob
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
import zlib
from pathlib import Path

MIB = 1024 * 1024
SECTOR = 512

# GPT partition type GUIDs (Linux filesystem / EFI system / basic data).
TYPE_LINUX = "0fc63daf-8483-4772-8e79-3d69d8477de4"
TYPE_ESP = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
TYPE_DATA = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"


def run(cmd, **kwargs):
    cmd = [str(item) for item in cmd]
    proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if proc.returncode != 0:
        sys.exit(f"mkimage: command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


def part_guid(image_name, part_name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"deepos:{image_name}:{part_name}"))


def gpt_type_for(fstype):
    if fstype == "fat32":
        return TYPE_ESP
    if fstype == "squashfs":
        return TYPE_LINUX
    return TYPE_DATA


def layout_partitions(layout, size_mib):
    """Assign start LBA / size for every partition, honouring fill:true."""
    sector = layout.get("sector", SECTOR)
    align = layout.get("align_mib", 1) * MIB // sector
    cursor = align  # 1 MiB of headroom for the GPT itself
    # The Rockchip boot chain lives below the first partition: idbloader.img at
    # 32 KiB (sector 64) and u-boot.itb at 8 MiB (sector 16384). Partitions that
    # must not cover it declare "start_mib" explicitly (BOOT starts at 16 MiB).
    parts = []
    used = 0
    for spec in layout["partitions"]:
        part_mib = spec["size_mib"]
        if spec.get("fill"):
            if part_mib:
                raise SystemExit("mkimage: fill partition must have size_mib 0")
            part_mib = None
        if part_mib is not None:
            used += part_mib
        parts.append(dict(spec, size_mib=part_mib))
    if size_mib is None or size_mib < used + 8:
        raise SystemExit(f"mkimage: image too small ({size_mib} MiB) for layout (needs > {used + 8} MiB)")
    # Anything below the first partition start is reserved for the GPT and the
    # Rockchip boot chain (idbloader at 32 KiB, u-boot.itb at 8 MiB), so the
    # fill partition may only use what is left after that reservation.
    explicit = [int(spec.get("start_mib", 0)) for spec in layout["partitions"] if spec.get("start_mib")]
    reserved = max(explicit) if explicit else layout.get("align_mib", 1)
    fill = size_mib - used - reserved
    if fill <= 0:
        raise SystemExit(f"mkimage: no room left for the fill partition ({fill} MiB)")
    for part in parts:
        if part["size_mib"] is None:
            part["size_mib"] = fill
        sectors = part["size_mib"] * MIB // sector
        cursor = (cursor + align - 1) // align * align
        if part.get("start_mib"):
            want = int(part["start_mib"]) * MIB // sector
            cursor = (want + align - 1) // align * align
        part["start_lba"] = cursor
        part["sectors"] = sectors
        part["byte_offset"] = cursor * sector
        cursor += sectors
    return parts


def write_gpt(image, image_name, parts, total_sectors):
    """Write protective MBR + primary/backup GPT and verify the entries CRC."""
    sector = SECTOR
    entry_size = 128
    entry_count = 32  # 4 KiB of entries, the conventional minimum

    blob = bytearray(entry_size * entry_count)
    for index, part in enumerate(parts):
        off = index * entry_size
        blob[off:off + 16] = uuid.UUID(gpt_type_for(part["type"])).bytes_le
        blob[off + 16:off + 32] = uuid.UUID(part_guid(image_name, part["name"])).bytes_le
        first = part["start_lba"]
        last = first + part["sectors"] - 1
        struct.pack_into("<QQQ", blob, off + 32, first, last, 0)
        name = part["label"].encode("utf-16-le")[:70]
        blob[off + 56:off + 56 + len(name)] = name

    entries_crc = zlib.crc32(bytes(blob)) & 0xFFFFFFFF
    disk_guid = uuid.UUID(part_guid(image_name, "disk"))
    entries_sectors = entry_count * entry_size // sector

    def header(current_lba, entries_lba):
        raw = struct.pack(
            "<8sIIIIQQQQ16sQIII",
            b"EFI PART", 0x00010000, 92, 0, 0,
            current_lba, total_sectors - 1,
            2 + entries_sectors, total_sectors - 2 - entries_sectors,
            disk_guid.bytes_le,
            entries_lba, entry_count, entry_size, entries_crc,
        )
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        return raw[:16] + struct.pack("<I", crc) + raw[20:]

    backup_entries_lba = total_sectors - 1 - entries_sectors
    primary = header(1, 2)
    backup = header(total_sectors - 1, backup_entries_lba)

    image.seek(0)
    image.write(bytes(34 * sector))
    image.seek(sector)
    image.write(primary)
    image.seek(2 * sector)
    image.write(blob)
    image.seek((total_sectors - 34) * sector)
    image.write(bytes(34 * sector))
    image.seek(backup_entries_lba * sector)
    image.write(blob)
    image.seek((total_sectors - 1) * sector)
    image.write(backup)
    image.seek(0)
    image.write(protective_mbr(total_sectors))
    image.flush()

    # Self-check: a short write here would produce a card that no longer boots.
    image.seek(2 * sector)
    written = image.read(entry_size * entry_count)
    if len(written) != entry_size * entry_count or zlib.crc32(written) & 0xFFFFFFFF != entries_crc:
        raise SystemExit("mkimage: GPT entries CRC mismatch right after writing the image")
    image.seek((total_sectors - 1) * sector)
    if image.read(8) != b"EFI PART":
        raise SystemExit("mkimage: backup GPT header is missing after writing the image")


def protective_mbr(total_sectors):
    mbr = bytearray(SECTOR)
    mbr[446:462] = struct.pack("<B3sB3sII", 0x00, b"\x00\x02\x00", 0xEE, b"\xff\xff\xff",
                              1, min(total_sectors - 1, 0xFFFFFFFF))
    mbr[510:512] = b"\x55\xaa"
    return bytes(mbr)





def make_fat32(path, label, mib, boot_dir):
    run(["mkfs.vfat", "-F", "32", "-n", label, path])
    if not boot_dir:
        return
    boot = Path(boot_dir)
    if not boot.is_dir():
        raise SystemExit(f"mkimage: --boot is not a directory: {boot}")
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    items = sorted(glob.glob(str(boot / "*")))
    if not items:
        return
    run(["mcopy", "-s", "-i", path, *items, "::"], env=env)


def make_squashfs(path, label, mib, source):
    if not source:
        # empty filesystem still gets a valid superblock, useful for tests
        source = tempfile.mkdtemp(prefix="deepos-empty-")
    src = Path(source)
    if not src.exists():
        raise SystemExit(f"mkimage: squashfs source missing: {source}")
    if src.is_file():
        # A ready image (build/rootfs.squashfs from tools/build-rootfs.sh): copy it
        # as-is. Packing a file with mksquashfs would put that file *inside* a new
        # filesystem instead of using its contents.
        with open(path, "r+b") as dst, src.open("rb") as handle:
            shutil.copyfileobj(handle, dst, 4 * MIB)
            dst.truncate(src.stat().st_size)
            dst.flush()
            os.fsync(dst.fileno())
        return
    run(["mksquashfs", str(src), path, "-noappend", "-quiet", "-comp", "zstd", "-no-progress"])


def make_ext4(path, label, mib, source):
    args = ["mkfs.ext4", "-q", "-F", "-L", label, "-O", "^metadata_csum_seed"]
    if source:
        args += ["-d", source]
    run(args + [path])


def make_exfat(path, label, mib, source):
    run(["mkfs.exfat", "-L", label, path])
    if source:
        raise SystemExit("mkimage: copying files into exFAT is not supported yet (mount it on the device)")


# Rockchip boot chain: idbloader (DDR init + SPL) at 32 KiB, U-Boot proper at 8 MiB.
LOADER_OFFSETS = {
    "idbloader.img": 32 * 1024,
    "u-boot.itb": 8 * 1024 * 1024,
}


def write_loader(image, loader_dir):
    """Place a Rockchip boot chain into the unpartitioned area of the image.

    Both files are optional individually, but at least one must be present: an
    image without a loader cannot boot this SoC (the BootROM only understands
    the Rockchip ID block format).
    """
    found = 0
    for name, offset in LOADER_OFFSETS.items():
        path = loader_dir / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) > 8 * 1024 * 1024:
            raise SystemExit(f"mkimage: {name} is suspiciously large ({len(data)} B)")
        image.seek(offset)
        image.write(data)
        found += 1
    if not found:
        raise SystemExit(f"mkimage: no idbloader.img or u-boot.itb in {loader_dir}")
    return found

def build(args):
    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    size_mib = args.size_mib
    if size_mib is None:
        size_mib = sum(p["size_mib"] for p in layout["partitions"] if not p.get("fill")) + 8192
    parts = layout_partitions(layout, size_mib)
    end_sector = max(p["start_lba"] + p["sectors"] for p in parts)
    total_sectors = max(size_mib * MIB // SECTOR, end_sector)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    sources = {
        "fat32": args.boot,
        "squashfs": args.sys_a,
        "ext4": args.data,
        "exfat": None,
    }
    if args.sys_b:
        sources_b = args.sys_b
    else:
        sources_b = args.sys_a

    with open(out, "w+b") as image:
        image.truncate(total_sectors * SECTOR)
        for part in parts:
            path = out.with_suffix(out.suffix + f".{part['name'].lower()}")
            path.unlink(missing_ok=True)
            # temp files are sparse-sized so mkfs sees the real partition size
            with open(path, "wb") as tmp:
                tmp.truncate(part["sectors"] * SECTOR)
            fstype = part["type"]
            if fstype == "squashfs":
                src = sources_b if part["name"] == "SYS_B" else sources["squashfs"]
                make_squashfs(path, part["label"], part["size_mib"], src)
            elif fstype == "fat32":
                make_fat32(path, part["label"], part["size_mib"], sources["fat32"])
            elif fstype == "ext4":
                make_ext4(path, part["label"], part["size_mib"], sources["ext4"])
            elif fstype == "exfat":
                make_exfat(path, part["label"], part["size_mib"], None)
            else:
                raise SystemExit(f"mkimage: unknown filesystem {fstype}")
            written = path.stat().st_size
            if written > part["sectors"] * SECTOR:
                raise SystemExit(f"mkimage: {part['name']} filesystem ({written} B) does not fit "
                                 f"in {part['sectors'] * SECTOR} B")
            with open(path, "rb") as src:
                image.seek(part["byte_offset"])
                shutil.copyfileobj(src, image, 4 * MIB)
            path.unlink()

        if args.loader:
            write_loader(image, Path(args.loader))

        write_gpt(image, layout["name"], parts, total_sectors)
        image.flush()
        os.fsync(image.fileno())

    report(out, layout, parts, size_mib)
    return out


def report(path, layout, parts, size_mib):
    digest = hashlib_sha256(path)
    print(f"image   {path}  {size_mib} MiB  sha256={digest}")
    for part in parts:
        print(f"  {part['name']:<6} {part['type']:<9} start={part['start_lba']:>8} "
              f"sectors={part['sectors']:>8} label={part['label']}")


def hashlib_sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(4 * MIB), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a DEEPoS GPT image")
    parser.add_argument("--layout", default=str(Path(__file__).resolve().parents[1] / "board/r36s-v20/layout.json"))
    parser.add_argument("--out", default="build/deepos-r36s-v20.img")
    parser.add_argument("--size-mib", type=int, default=None, help="total image size; ROMS fills the rest")
    parser.add_argument("--boot", default=None, help="directory copied into the FAT32 BOOT partition")
    parser.add_argument("--sys-a", default=None, help="rootfs tree or squashfs for SYS_A")
    parser.add_argument("--sys-b", default=None, help="rootfs tree or squashfs for SYS_B (default: same as A)")
    parser.add_argument("--data", default=None, help="directory laid down as the initial DATA contents")
    parser.add_argument("--loader", default=None, help="directory with idbloader.img / u-boot.itb (Rockchip boot chain)")

    args = parser.parse_args(argv)
    build(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
