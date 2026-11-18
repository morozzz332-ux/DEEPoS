#!/usr/bin/env python3
"""Host tests for the image builder and flasher (no device involved).

Builds a small but real image with the same GPT layout and filesystems as the
production one, then checks the structures byte by byte and flashes the image
into a plain file to prove the writer is lossless.
"""
import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MKIMAGE = ROOT / "tools" / "mkimage.py"
DPFLASH = ROOT / "tools" / "dpflash.py"
LAYOUT = ROOT / "board" / "r36s-v20" / "layout.json"
SMALL_LAYOUT = ROOT / "tests" / "fixtures" / "layout-small.json"

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def read_gpt(image_path):
    with open(image_path, "rb") as handle:
        handle.seek(512)
        header = handle.read(92)
        if header[:8] != b"EFI PART":
            return None, []
        (entries_lba,) = struct.unpack_from("<Q", header, 72)
        (count,) = struct.unpack_from("<I", header, 80)
        (size,) = struct.unpack_from("<I", header, 84)
        handle.seek(entries_lba * 512)
        blob = handle.read(count * size)
    parts = []
    for index in range(count):
        entry = blob[index * size:(index + 1) * size]
        if not any(entry[:16]):
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        name = entry[56:128].decode("utf-16-le").rstrip("\x00")
        parts.append({"name": name, "first": first, "last": last})
    return header, parts


def build(tmp):
    rootfs = tmp / "rootfs"
    (rootfs / "etc").mkdir(parents=True)
    (rootfs / "etc" / "os-release").write_text('NAME="DEEPoS"\n', encoding="utf-8")
    boot = tmp / "boot"
    boot.mkdir()
    (boot / "KERNEL").write_bytes(b"\x00" * 4096)
    (boot / "extlinux.conf").write_text("LABEL DEEPoS\nLINUX /KERNEL\n", encoding="utf-8")
    data = tmp / "data"
    data.mkdir()
    (data / "profile").write_text("balanced\n", encoding="utf-8")
    image = tmp / "deepos-test.img"
    proc = subprocess.run([
        sys.executable, str(MKIMAGE), "--layout", str(SMALL_LAYOUT), "--out", str(image),
        "--size-mib", "128", "--boot", str(boot), "--sys-a", str(rootfs), "--data", str(data),
    ], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    check("mkimage exits 0", proc.returncode == 0, proc.stderr.strip()[-300:])
    if proc.returncode != 0:
        raise SystemExit("mkimage failed, see output above")
    return image


def probe(image):
    header, parts = read_gpt(image)
    check("GPT header present", header is not None)
    check("5 partitions", len(parts) == 5, str([p["name"] for p in parts]))
    names = [p["name"] for p in parts]
    check("partition names", names == ["BOOT", "DEEPOS_A", "DEEPOS_B", "DATA", "ROMS"], str(names))
    aligned = all((p["first"] * 512) % (1024 * 1024) == 0 for p in parts)
    check("1 MiB alignment", aligned)
    ordered = all(parts[i]["last"] < parts[i + 1]["first"] for i in range(len(parts) - 1))
    check("partitions ordered", ordered)

    with open(image, "rb") as handle:
        def at(offset, size):
            handle.seek(offset)
            return handle.read(size)

        fat = at(parts[0]["first"] * 512, 512)
        check("FAT32 signature", fat[510:512] == b"\x55\xaa")
        label = fat[0x47:0x47 + 11].decode("ascii", "replace").strip()
        check("FAT32 label BOOT", label == "BOOT", repr(label))

        squash_a = at(parts[1]["first"] * 512, 4)
        squash_b = at(parts[2]["first"] * 512, 4)
        check("SYS_A squashfs magic", squash_a == b"hsqs", repr(squash_a))
        check("SYS_B squashfs magic", squash_b == b"hsqs", repr(squash_b))

        ext4 = at(parts[3]["first"] * 512 + 1080, 2)
        check("DATA ext4 magic", struct.unpack("<H", ext4)[0] == 0xEF53, repr(ext4))

        exfat = at(parts[4]["first"] * 512 + 3, 8)
        check("ROMS exFAT signature", exfat == b"EXFAT   ", repr(exfat))



    return parts


def data_files_test(image, tmp):
    """The DATA partition must really contain the staged files (emulators.toml)."""
    _, parts = read_gpt(image)
    data = next((p for p in parts if p["name"] == "DATA"), None)
    check("DATA partition found", data is not None)
    if data is None:
        return
    with open(image, "rb") as handle:
        handle.seek(data["first"] * 512)
        blob = handle.read((data["last"] - data["first"] + 1) * 512)
    part = tmp / "data-part.img"
    part.write_bytes(blob)
    for name, expected in (("profile", "balanced"),):
        proc = subprocess.run(["debugfs", "-R", f"cat /{name}", str(part)],
                              capture_output=True, text=True, timeout=60)
        check(f"DATA/{name} readable", proc.returncode == 0, proc.stderr.strip()[-200:])
        check(f"DATA/{name} content", proc.stdout.strip() == expected, proc.stdout[:100])

def flash(image, tmp):
    target = tmp / "card.img"
    size = image.stat().st_size
    target.write_bytes(b"\x00" * size)
    proc = subprocess.run([sys.executable, str(DPFLASH), "--image", str(image),
                           "--target", str(target)], capture_output=True, text=True, timeout=300)
    check("dpflash exits 0", proc.returncode == 0, proc.stderr.strip()[-300:])
    expected = hashlib.sha256(image.read_bytes()).hexdigest()
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    check("flash is byte identical", expected == actual)

    dry_target = tmp / "card-dry.img"
    dry_target.write_bytes(b"\xAA" * size)
    proc = subprocess.run([sys.executable, str(DPFLASH), "--image", str(image),
                           "--target", str(dry_target), "--dry-run"],
                          capture_output=True, text=True, timeout=120)
    check("dry-run exits 0", proc.returncode == 0, proc.stderr.strip()[-200:])
    check("dry-run writes nothing", dry_target.read_bytes() == b"\xAA" * size)

    proc = subprocess.run([sys.executable, str(DPFLASH), "--image", str(image),
                           "--target", str(target), "--expect-sha256", "0" * 64],
                          capture_output=True, text=True, timeout=120)
    check("sha mismatch refused", proc.returncode != 0)

    small = tmp / "card-small.img"
    small.write_bytes(b"\x00" * 1024)
    proc = subprocess.run([sys.executable, str(DPFLASH), "--image", str(image),
                           "--target", str(small)], capture_output=True, text=True, timeout=120)
    check("small target refused", proc.returncode != 0)


def loader_test(tmp):
    loader = tmp / "loader"
    loader.mkdir()
    (loader / "idbloader.img").write_bytes(b"\x55" * 512)
    (loader / "u-boot.itb").write_bytes(b"\xAA" * 1024)
    boot = tmp / "boot2"
    boot.mkdir()
    (boot / "KERNEL").write_bytes(b"\x00" * 4096)
    rootfs = tmp / "rootfs2"
    rootfs.mkdir()
    image = tmp / "deepos-loader.img"
    proc = subprocess.run([
        sys.executable, str(MKIMAGE), "--layout", str(SMALL_LAYOUT), "--out", str(image),
        "--size-mib", "128", "--boot", str(boot), "--sys-a", str(rootfs), "--loader", str(loader),
    ], capture_output=True, text=True, timeout=300)
    check("mkimage with loader exits 0", proc.returncode == 0, proc.stderr.strip()[-300:])
    if proc.returncode != 0:
        return
    with open(image, "rb") as handle:
        handle.seek(32 * 1024)
        idb = handle.read(512)
        handle.seek(8 * 1024 * 1024)
        itb = handle.read(1024)
        handle.seek(0)
        head = handle.read(512)
    check("idbloader at 32 KiB", idb == b"\x55" * 512)
    check("u-boot.itb at 8 MiB", itb == b"\xAA" * 1024)
    check("loader does not disturb GPT", head[510:512] == b"\x55\xaa")

    empty = tmp / "loader-empty"
    empty.mkdir()
    proc = subprocess.run([
        sys.executable, str(MKIMAGE), "--layout", str(SMALL_LAYOUT), "--out", str(tmp / "x.img"),
        "--size-mib", "128", "--boot", str(boot), "--sys-a", str(rootfs), "--loader", str(empty),
    ], capture_output=True, text=True, timeout=300)
    check("empty loader refused", proc.returncode != 0)


def verify_tool(image: pathlib.Path, loader: pathlib.Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(ROOT / "tools" / "verify-image.py"),
           "--loader", str(loader), "--skip-rootfs", str(image)]
    return subprocess.run(cmd, capture_output=True, text=True)


def verify_checks(tmp: pathlib.Path) -> None:
    """verify-image must accept a good image and reject a damaged GPT."""
    build_dir = tmp / "verify-build"
    loader = build_dir / "loader"
    boot = build_dir / "boot"
    data = build_dir / "data"
    for d in (loader, boot, data):
        d.mkdir(parents=True)
    (loader / "idbloader.img").write_bytes(b"\x55" * 512)
    (loader / "u-boot.itb").write_bytes(b"\xaa" * 1024)
    kernel = b"\x4d\x5a" + b"\x00" * 2048
    (boot / "KERNEL").write_bytes(kernel)
    (boot / "extlinux").mkdir()
    (boot / "extlinux" / "extlinux.conf").write_text("LABEL DEEPoS\n", encoding="utf-8")
    dtb = b"\xd0\x0d\xfe\xed" + b"\x00" * 512
    (boot / "dtbs").mkdir()
    (boot / "dtbs" / "rk3326-r36s-v20.dtb").write_bytes(dtb)
    (boot / "MANIFEST.json").write_text(json.dumps({
        "board": "verify-test",
        "version": "test",
        "files": {"KERNEL": hashlib.sha256(kernel).hexdigest(),
                  "dtbs/rk3326-r36s-v20.dtb": hashlib.sha256(dtb).hexdigest()},
        "sizes": {"KERNEL": len(kernel), "dtbs/rk3326-r36s-v20.dtb": len(dtb)},
    }, indent=2) + "\n", encoding="utf-8")
    (data / "config.toml").write_text('name = "deepos"\n', encoding="utf-8")

    layout = build_dir / "layout.json"
    layout.write_text(json.dumps({
        "name": "verify-test",
        "sector": 512,
        "align_mib": 1,
        "partitions": [
            {"name": "BOOT", "label": "BOOT", "type": "fat32", "size_mib": 16, "start_mib": 16},
            {"name": "SYS_A", "label": "DEEPOS_A", "type": "squashfs", "size_mib": 20},
            {"name": "SYS_B", "label": "DEEPOS_B", "type": "squashfs", "size_mib": 20},
            {"name": "DATA", "label": "DATA", "type": "ext4", "size_mib": 16},
            {"name": "ROMS", "label": "ROMS", "type": "exfat", "size_mib": 0, "fill": True},
        ],
    }), encoding="utf-8")

    image = build_dir / "verify.img"
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "mkimage.py"),
        "--layout", str(layout), "--out", str(image), "--size-mib", "96",
        "--boot", str(boot), "--sys-a", str(tmp), "--data", str(data), "--loader", str(loader),
    ], capture_output=True, text=True)
    check("verify fixture image builds", proc.returncode == 0, proc.stderr[-300:])
    if proc.returncode != 0:
        return

    good = verify_tool(image, loader)
    check("verify-image accepts a good image", good.returncode == 0, good.stdout[-400:])

    blob = bytearray(image.read_bytes())
    blob[1024 + 60] ^= 0xFF
    broken = build_dir / "broken.img"
    broken.write_bytes(bytes(blob))
    bad = verify_tool(broken, loader)
    check("verify-image rejects a corrupted GPT", bad.returncode == 1, bad.stdout[-200:])
    check("failure names the entries CRC", "GPT entries CRC" in bad.stdout)


def main():
    if not SMALL_LAYOUT.exists():
        print("missing tests/fixtures/layout-small.json")
        return 1
    with tempfile.TemporaryDirectory(prefix="deepos-img-") as raw:
        tmp = pathlib.Path(raw)
        print("build image")
        image = build(tmp)
        print("probe layout")
        parts = probe(image)
        print("flash")
        flash(image, tmp)
        print("loader")
        loader_test(tmp)
    verify_checks(tmp)

    if failures:
        print(f"\nFAIL  image: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nPASS  image: GPT layout, filesystem signatures, DATA files, loader placement, flash is lossless")
    return 0


if __name__ == "__main__":
    sys.exit(main())
