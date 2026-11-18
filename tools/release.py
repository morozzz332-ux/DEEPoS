#!/usr/bin/env python3
"""Collect the artefacts of one build into docs/RELEASE.md.

The file answers "what exactly is on the card" without guessing: image sha256,
kernel/dtb/rootfs sizes, BOOT version and the git revision the build came from.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

REQUIRED = ("kernel", "dtb", "boot", "rootfs", "image")


def sha256_of(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info(root):
    def run(*args):
        try:
            out = subprocess.run(["git", "-C", str(root)] + list(args),
                                 capture_output=True, text=True, check=True)
            return out.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    return run("rev-parse", "--short", "HEAD"), run("rev-parse", "--abbrev-ref", "HEAD")


def boot_version(boot_dir):
    manifest = boot_dir / "MANIFEST.json"
    if not manifest.exists():
        return "?"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "?")
    except (OSError, ValueError):
        return "?"


def collect(args):
    root = pathlib.Path(args.root).resolve()
    paths = {
        "kernel": root / args.kernel,
        "dtb": root / args.dtb,
        "boot": root / args.boot,
        "rootfs": root / args.rootfs,
        "image": root / args.image,
        "idbloader": root / args.loader / "idbloader.img",
        "u-boot": root / args.loader / "u-boot.itb",
    }
    missing = [name for name in REQUIRED if not paths[name].exists()]
    if missing and not args.allow_missing:
        print("missing artefacts: " + ", ".join(missing), file=sys.stderr)
        return 2

    rows = []
    for name, path in paths.items():
        if not path.exists():
            rows.append((name, "—", "—", "missing"))
            continue
        if path.is_dir():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            digits = "dir"
        else:
            size = path.stat().st_size
            digits = sha256_of(path)
        rows.append((name, f"{size}", digits, str(path.relative_to(root))))

    commit, branch = git_info(root)
    lines = [
        "# DEEPoS release",
        "",
        f"- image sha256: `{rows[4][2]}`",
        f"- image size: {rows[4][1]} bytes",
        f"- BOOT version: `{boot_version(paths['boot'])}`",
        f"- git: `{branch or '?'}` at `{commit or '?'}`",
        "",
        "| artefact | bytes | sha256 | path |",
        "|---|---|---|---|",
    ]
    for name, size, digest, rel in rows:
        lines.append(f"| {name} | {size} | `{digest}` | `{rel}` |")
    lines += [
        "",
        "Проверки перед записью:",
        "",
        "```sh",
        "python3 tools/preflight.py --root .",
        "python3 tools/verify-image.py --loader build/uboot build/deepos-r36s-v20.img",
        "python3 tools/dpflash.py --list          # номер карты, не гадать",
        "python3 tools/dpflash.py --image build/deepos-r36s-v20.img --target \\\\.\\PhysicalDriveN --expect-sha256 <sha выше>",
        "```",
        "",
    ]
    return "\n".join(lines), rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write docs/RELEASE.md for the current build")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="docs/RELEASE.md")
    parser.add_argument("--kernel", default="build/kernel/Image")
    parser.add_argument("--dtb", default="build/kernel/rk3326-r36s-v20.dtb")
    parser.add_argument("--boot", default="build/boot")
    parser.add_argument("--rootfs", default="build/rootfs.squashfs")
    parser.add_argument("--image", default="build/deepos-r36s-v20.img")
    parser.add_argument("--loader", default="build/uboot")
    parser.add_argument("--allow-missing", action="store_true",
                        help="still write the report when an artefact is absent (tests)")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args(argv)

    result = collect(args)
    if isinstance(result, int):
        return result
    text, rows = result
    if args.stdout:
        print(text)
    else:
        out = pathlib.Path(args.root).resolve() / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out} ({len(rows)} artefacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
