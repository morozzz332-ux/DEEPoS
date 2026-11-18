#!/usr/bin/env python3
"""Release report must describe artefacts honestly, including missing ones."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path("/w")


def run(args, cwd=ROOT):
    return subprocess.run([sys.executable, "tools/release.py"] + args,
                          cwd=cwd, capture_output=True, text=True)


def make_tree(tmp: pathlib.Path):
    (tmp / "build/kernel").mkdir(parents=True)
    (tmp / "build/kernel/Image").write_bytes(b"K" * 4096)
    (tmp / "build/kernel/rk3326-r36s-v20.dtb").write_bytes(b"D" * 256)
    (tmp / "build/boot").mkdir(parents=True)
    (tmp / "build/boot/MANIFEST.json").write_text(
        json.dumps({"version": "9.9-test", "files": {}}), encoding="utf-8")
    (tmp / "build/rootfs.squashfs").write_bytes(b"S" * 8192)
    (tmp / "build/deepos-r36s-v20.img").write_bytes(b"I" * 16384)
    (tmp / "build/uboot").mkdir(parents=True)
    (tmp / "build/uboot/idbloader.img").write_bytes(b"L" * 512)
    (tmp / "build/uboot/u-boot.itb").write_bytes(b"B" * 1024)


def main():
    failures = []
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        make_tree(tmp)
        res = run(["--root", str(tmp), "--out", "RELEASE.md"])
        if res.returncode != 0:
            failures.append(f"release run failed: {res.stderr.strip()[:200]}")
            print("FAIL release run")
            return 1
        text = (tmp / "RELEASE.md").read_text(encoding="utf-8")
        print("wrote:", "RELEASE.md" in res.stdout)

        if "9.9-test" not in text:
            failures.append("BOOT version missing from the report")
        if "16384" not in text:
            failures.append("image size missing")
        if "K" * 4 in text:
            failures.append("report embeds artefact bytes")
        if text.count("| ") < 8:
            failures.append("artefact table looks empty")
        sha = __import__("hashlib").sha256(b"I" * 16384).hexdigest()
        if sha not in text:
            failures.append("image sha256 missing")
        for word in ("preflight.py", "verify-image.py", "dpflash.py"):
            if word not in text:
                failures.append(f"next-step command {word} missing")

        (tmp / "build/deepos-r36s-v20.img").unlink()
        res2 = run(["--root", str(tmp), "--out", "R2.md"])
        if res2.returncode != 2:
            failures.append(f"missing image should exit 2, got {res2.returncode}")
        res3 = run(["--root", str(tmp), "--out", "R3.md", "--allow-missing"])
        if res3.returncode != 0:
            failures.append("--allow-missing should still write the report")

    if failures:
        for f in failures:
            print("  fail:", f)
        print("FAIL  release")
        return 1
    print("PASS  release: sha256, sizes, boot version, next-step commands, missing-artefact guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
