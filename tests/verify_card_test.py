#!/usr/bin/env python3
"""Checks verify-card.py against a flashed image and a damaged one."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WORK = pathlib.Path(tempfile.mkdtemp(prefix="verifycard-"))


def run(args, expect=0):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if expect is not None and proc.returncode != expect:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"{args[0]} exited {proc.returncode}, expected {expect}")
    return proc.stdout + proc.stderr


def build_image():
    layout = json.loads((ROOT / "tests/fixtures/layout-small.json").read_text())
    boot = WORK / "boot"
    (boot / "extlinux").mkdir(parents=True)
    (boot / "extlinux/extlinux.conf").write_text(
        "LABEL DEEPoS\nLINUX /KERNEL\nFDT /dtbs/rk3326-r36s-v20.dtb\n")
    (boot / "KERNEL").write_bytes(b"\x01" * (1024 * 1024))
    (boot / "dtbs").mkdir()
    (boot / "dtbs/rk3326-r36s-v20.dtb").write_bytes(b"\xd0\x0d\xfe\xed" + bytes(2048))
    sysfs = WORK / "sys"
    sysfs.mkdir()
    data = WORK / "data"
    data.mkdir()
    image = WORK / "card.img"
    run([PY, "tools/mkimage.py", "--layout", str(ROOT / "tests/fixtures/layout-small.json"),
         "--size-mib", "128",
         "--out", str(image), "--boot", str(boot), "--sys-a", str(sysfs),
         "--sys-b", str(sysfs), "--data", str(data)])
    return image


def flash(image):
    target = WORK / "target.img"
    target.write_bytes(b"\x00" * image.stat().st_size)
    run([PY, "tools/dpflash.py", "--image", str(image), "--target", str(target),
         "--no-defer-table"])
    return target


def main():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name} {detail}")
            failures.append(name)

    image = build_image()
    target = flash(image)

    out = run([PY, "tools/verify-card.py", "--target", str(target)])
    check("clean card passes", "PASS  card:" in out, out.strip().splitlines()[-1:])

    with open(target, "r+b") as handle:
        handle.seek(2 * 512 + 40)
        byte = handle.read(1)
        handle.seek(2 * 512 + 40)
        handle.write(bytes([byte[0] ^ 0xFF]))
    out = run([PY, "tools/verify-card.py", "--target", str(target)], expect=1)
    check("damaged entries fail the CRC", "partition entries CRC" in out)

    target2 = flash(image)
    out = run([PY, "tools/verify-card.py", "--target", str(target2),
               "--image", str(image)])
    check("--image compares the prefix", "card prefix matches the image" in out)

    with open(target2, "r+b") as handle:
        handle.seek(1000)
        handle.write(b"\xff" * 8)
    out = run([PY, "tools/verify-card.py", "--target", str(target2),
               "--image", str(image)], expect=1)
    check("--image catches a stray write", "card prefix matches the image" in out)

    print()
    if failures:
        print(f"FAIL  verify-card: {len(failures)} check(s) failed")
        return 1
    print("PASS  verify-card: clean card, damaged CRC, image prefix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
