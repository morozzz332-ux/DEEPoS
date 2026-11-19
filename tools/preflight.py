#!/usr/bin/env python3
"""DEEPoS preflight: one command that says whether the build is ready to flash.

Checks the artefacts the way the boot chain uses them, not just their presence:

  * kernel Image is plausible and BOOT/KERNEL matches its MANIFEST sha256
  * the DTB in BOOT really is our board (compatible strings) and is named
    exactly as extlinux.conf expects - a typo here means no boot at all
  * the rootfs carries everything rcS is going to exec, including the
    executable bit on rcS itself
  * Rockchip loaders are present
  * the final image passes tools/verify-image.py (GPT, backup GPT, FS signatures)

Usage:
    python3 tools/preflight.py [--root DIR] [--image FILE] [--loader DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess

from loader_donor import donor_region
from mkboot import BOOT_SCRIPT, ROOTDIR_INITRD, rootdir_initramfs, valid_boot_script, validate_extlinux
from v20_display import ARCHR_COMPATIBLE, display_checks, get_string
import sys
from pathlib import Path

MIN_KERNEL = 10 * 1024 * 1024
REQUIRED_ROOTFS = [
    "sbin/init",
    "bin/busybox",
    "usr/bin/launcher",
    "usr/bin/modd",
    "usr/bin/saved",
    "usr/bin/updatr",
    "etc/init.d/rcS",
    "etc/inittab",
    "etc/os-release",
]


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.checks = 0

    def ok(self, text: str) -> None:
        self.checks += 1
        print(f"ok    {text}")

    def fail(self, text: str) -> None:
        self.checks += 1
        self.failures += 1
        print(f"FAIL  {text}")

    def check(self, cond: bool, text: str) -> bool:
        self.ok(text) if cond else self.fail(text)
        return cond


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_extlinux(conf: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, _, tail = line.partition(" ")
        if head in ("LABEL", "LINUX", "FDT", "FDTDIR", "INITRD", "APPEND"):
            out.setdefault(head, tail.strip())
    return out


def boot_checks(rep: Report, boot: Path, kernel: Path, dtb: Path, *, require_script=False) -> None:
    rep.check(kernel.is_file(), f"kernel image present: {kernel}")
    if kernel.is_file():
        size = kernel.stat().st_size
        rep.check(size >= MIN_KERNEL,
                  f"kernel size {size} bytes (>= {MIN_KERNEL})")

    rep.check(dtb.is_file(), f"device tree present: {dtb}")
    if dtb.is_file():
        for ok, name in display_checks(dtb, kernel):
            rep.check(ok, name)

    conf = boot / "extlinux" / "extlinux.conf"
    if not rep.check(conf.is_file(), f"extlinux.conf present: {conf}"):
        return
    has_rootdir = False
    try:
        board = get_string(dtb, "/", "compatible").split() if dtb.is_file() else ()
        has_rootdir = validate_extlinux(conf.read_text(encoding="utf-8"),
                                       archr_v20=ARCHR_COMPATIBLE in board)
    except ValueError as exc:
        rep.fail(str(exc))
    else:
        rep.check(True, "extlinux APPEND and root selector are valid")
    rootdir = boot / ROOTDIR_INITRD
    if has_rootdir:
        rep.check(rootdir.is_file() and rootdir.read_bytes() == rootdir_initramfs(),
                  "BOOT contains the /root mountpoint initramfs")
    script = boot / BOOT_SCRIPT
    if require_script:
        rep.check(script.is_file() and valid_boot_script(script.read_bytes()),
                  "BOOT contains a valid boot.scr for the donor")
    entries = read_extlinux(conf)
    rep.check(entries.get("LABEL") == "DEEPoS", f"extlinux label: {entries.get('LABEL')!r}")
    linux = entries.get("LINUX", "")
    rep.check(linux == "/KERNEL", f"extlinux loads {linux!r}")
    fdt = entries.get("FDT", "")
    rep.check(fdt.startswith("/dtbs/"), f"extlinux fdt {fdt!r}")
    if fdt.startswith("/dtbs/"):
        named = boot / fdt.lstrip("/")
        if rep.check(named.is_file(), f"fdt file exists: {named.name}"):
            rep.check(named.name == dtb.name,
                      f"fdt name matches built dtb ({dtb.name})")
            if dtb.is_file():
                rep.check(sha256(named) == sha256(dtb), "BOOT DTB sha256 matches built DTB")

    kboot = boot / "KERNEL"
    if rep.check(kboot.is_file(), "BOOT/KERNEL exists"):
        if kernel.is_file():
            rep.check(kboot.stat().st_size == kernel.stat().st_size,
                      "BOOT/KERNEL size equals build kernel")
        man = boot / "MANIFEST.json"
        if rep.check(man.is_file(), "BOOT/MANIFEST.json exists"):
            data = json.loads(man.read_text(encoding="utf-8"))
            files = data.get("files", {})
            if has_rootdir and rootdir.is_file():
                rep.check(sha256(rootdir) == files.get(ROOTDIR_INITRD),
                          "BOOT mountpoint initramfs sha256 matches manifest")
            if require_script and script.is_file():
                rep.check(sha256(script) == files.get(BOOT_SCRIPT),
                          "BOOT/boot.scr sha256 matches manifest")
            want = files.get("KERNEL")
            rep.check(bool(want), "manifest lists KERNEL sha256")
            if want:
                rep.check(sha256(kboot) == want, "BOOT/KERNEL sha256 matches manifest")


def rootfs_checks(rep: Report, root: Path, squash: Path) -> None:
    if not rep.check(squash.is_file(), f"rootfs image present: {squash}"):
        return
    try:
        listing = subprocess.run(
            ["unsquashfs", "-ll", str(squash)],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        rep.fail(f"unsquashfs cannot read {squash.name}: {exc}")
        return

    for rel in REQUIRED_ROOTFS:
        if rel == "sbin/init":
            # busybox init is a symlink in our rootfs
            rep.check(f"squashfs-root/sbin/init" in listing, "rootfs has sbin/init")
            continue
        rep.check(f"squashfs-root/{rel}" in listing, f"rootfs has {rel}")

    for line in listing.splitlines():
        if line.rstrip().endswith("squashfs-root/etc/init.d/rcS"):
            rep.check(line.lstrip().startswith("-rwx"), "rcS is executable")
            break
    else:
        rep.fail("rcS entry not found in the listing")


def loader_checks(rep: Report, loader: Path) -> None:
    for name, off in (("idbloader.img", 32 * 1024), ("u-boot.itb", 8 * 1024 * 1024)):
        path = loader / name
        if rep.check(path.is_file(), f"loader {name} present"):
            rep.check(path.stat().st_size > 1024, f"{name} is not empty")
            print(f"      {name}: {path.stat().st_size} bytes at offset {off}")


def image_checks(rep: Report, root: Path, image: Path, loader: Path, donor=None) -> None:
    if not image.is_file():
        rep.fail(f"image not built yet: {image}")
        return
    tool = root / "tools" / "verify-image.py"
    loader_flag = ["--loader-donor", str(donor)] if donor else ["--loader", str(loader)]
    cmd = [sys.executable, str(tool), *loader_flag, str(image)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    rep.check(proc.returncode == 0, f"verify-image: {tail}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repository root")
    ap.add_argument("--boot", default="build/boot")
    ap.add_argument("--kernel", default="build/kernel/Image")
    ap.add_argument("--dtb", default="build/kernel/rk3326-r36s-v20.dtb")
    ap.add_argument("--rootfs", default="build/rootfs.squashfs")
    loader_group = ap.add_mutually_exclusive_group()
    loader_group.add_argument("--loader", default="build/uboot")
    loader_group.add_argument("--loader-donor", type=Path)
    ap.add_argument("--image", default="build/deepos-r36s-v20.img")
    ap.add_argument("--skip-image", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    rep = Report()

    donor = root / args.loader_donor if args.loader_donor else None
    boot_checks(rep, root / args.boot, root / args.kernel, root / args.dtb,
                require_script=bool(donor))
    rootfs_checks(rep, root, root / args.rootfs)
    if donor:
        try:
            donor_region(donor)
        except (OSError, ValueError) as exc:
            rep.fail(f"donor loader: {exc}")
        else:
            rep.check(True, "Rockchip donor loader readable")
    else:
        loader_checks(rep, root / args.loader)
    if not args.skip_image:
        image_checks(rep, root, root / args.image, root / args.loader, donor)

    if rep.failures:
        print(f"PREFLIGHT: NO-GO ({rep.failures} of {rep.checks} checks failed)")
        return 1
    print(f"PREFLIGHT: GO ({rep.checks} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
