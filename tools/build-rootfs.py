#!/usr/bin/env python3
"""Build the DEEPoS root filesystem image (squashfs).

The `--label` value is only echoed (squashfs has no filesystem label; the
partition label DEEPOS_A/DEEPOS_B is set in the GPT by tools/mkimage.py).

The rootfs is a read-only squashfs stored inside the SYS_A / SYS_B partitions.
This tool only packs a prepared staging tree; it does not download or build
BusyBox/kernel (that is the job of the containerised image build).

Usage:
    build-rootfs.py --root <staging-dir> --out <file.squashfs> [--label DEEPOS_A]
                    [--check] [--list]

`--check` validates the staging tree layout before packing: it must contain
/sbin/init (or /init), /bin/busybox and the three module directories.
`--list` prints the packed file list (unsquashfs -l) after packing.
"""

import argparse
import os
import shutil
import subprocess
import sys

REQUIRED = [
    "sbin/init",
    "bin/busybox",
]

# App binaries are staged either next to their sources (test fixtures) or in
# /usr/bin (the real rootfs); both layouts are valid for the checker.
REQUIRED_ANY = [
    (("apps/modd/modd", "usr/bin/modd"), "modd"),
    (("apps/saved/saved", "usr/bin/saved"), "saved"),
        (("apps/updatr/updatr", "usr/bin/updatr"), "updatr"),
    (("apps/launcher/launcher", "usr/bin/launcher"), "launcher"),
    (("apps/playdemo/playdemo", "usr/bin/playdemo"), "playdemo"),
]


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)
    except FileNotFoundError:
        raise SystemExit(f"missing tool: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{exc.stderr or exc.stdout}")


def check_tree(root):
    problems = []
    if not os.path.isdir(root):
        raise SystemExit(f"staging dir does not exist: {root}")
    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(root, rel)):
            problems.append(f"missing {rel}")
    init = os.path.join(root, "sbin/init")
    if os.path.isfile(init) and not os.access(init, os.X_OK):
        problems.append("sbin/init is not executable")
    for candidates, name in REQUIRED_ANY:
        if not any(os.path.isfile(os.path.join(root, rel)) for rel in candidates):
            problems.append(f"missing {' or '.join(candidates)} ({name})")
    if problems:
        raise SystemExit("rootfs check failed:\n  " + "\n  ".join(problems))
    return True


def pack(root, out, label):
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    cmd = [
        "mksquashfs", root, tmp,
        "-noappend", "-quiet", "-no-progress",
        "-comp", "zstd", "-b", "262144",
    ]
    run(cmd)
    os.replace(tmp, out)
    return os.path.getsize(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="pack a DEEPoS rootfs into squashfs")
    ap.add_argument("--root", required=True, help="staging tree")
    ap.add_argument("--out", required=True, help="output .squashfs file")
    ap.add_argument("--label", default="DEEPOS_A", help="filesystem label")
    ap.add_argument("--check", action="store_true", help="validate staging tree first")
    ap.add_argument("--list", action="store_true", help="print packed file list")
    args = ap.parse_args(argv)

    if args.check:
        check_tree(args.root)
    if shutil.which("mksquashfs") is None:
        raise SystemExit("mksquashfs not found (install squashfs-tools)")

    size = pack(args.root, args.out, args.label)
    print(f"{args.out}: {size} bytes, label={args.label}")
    if args.list:
        res = run(["unsquashfs", "-l", args.out])
        sys.stdout.write(res.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
