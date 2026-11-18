#!/usr/bin/env python3
"""read-report.py must find BOOT/report on a card written from an image.

The console writes its diagnostics into BOOT/report; Windows frequently refuses
to give that partition a drive letter right after a raw flash, so the tool reads
the partition straight out of the GPT. This test builds a tiny image with a fake
report, flashes it to a file and checks that the report comes back.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIB = 1024 ** 2

checks = []


def check(name, ok, detail=""):
    checks.append((name, ok))
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' — ' + detail) if detail and not ok else ''}")
    return ok


def run(*args, **kwargs):
    return subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True, **kwargs)


def build_tree(work):
    boot = work / "boot"
    (boot / "extlinux").mkdir(parents=True)
    (boot / "dtbs").mkdir()
    (boot / "report").mkdir()
    (boot / "extlinux" / "extlinux.conf").write_text(
        "LABEL DEEPoS\nLINUX /KERNEL\nFDT /dtbs/rk3326-r36s-v20.dtb\n", encoding="utf-8")
    (boot / "KERNEL").write_bytes(b"\x01" * (2 * MIB))
    (boot / "dtbs" / "rk3326-r36s-v20.dtb").write_bytes(b"\xd0\x0d\xfe\xed" + bytes(1024))
    (boot / "report" / "checks.txt").write_text(
        "kernel=6.12.56\nverdict=ok\npanel=present\nmem_available_mb=560\nsoc_c=48\n",
        encoding="utf-8")
    (boot / "report" / "boot.txt").write_text("DEEPoS test boot\n", encoding="utf-8")
    (work / "sys").mkdir()
    (work / "data").mkdir()
    return boot


def main():
    with tempfile.TemporaryDirectory(prefix="read-report-") as tmp:
        work = pathlib.Path(tmp)
        boot = build_tree(work)
        image = work / "card.img"
        build = run(sys.executable, "tools/mkimage.py", "--out", str(image),
                    "--layout", "tests/fixtures/layout-small.json",
                    "--size-mib", "96", "--boot", str(boot),
                    "--sys-a", str(work / "sys"), "--data", str(work / "data"))
        if not check("image builds", build.returncode == 0, build.stderr[-300:]):
            return finish()
        target = work / "target.img"
        target.write_bytes(b"\x00" * image.stat().st_size)
        flash = run(sys.executable, "tools/dpflash.py", "--image", str(image),
                    "--target", str(target), "--no-defer-table")
        if not check("card flashes", flash.returncode == 0, flash.stderr[-300:]):
            return finish()

        listing = run(sys.executable, "tools/read-report.py", "--target", str(target),
                      "--list")
        ok = check("report listing works", listing.returncode == 0, listing.stderr[-300:])
        check("listing mentions the report files", "checks" in listing.stdout.lower())

        out = work / "out"
        copied = run(sys.executable, "tools/read-report.py", "--target", str(target),
                     "--out", str(out))
        check("report copies", copied.returncode == 0, copied.stderr[-300:])
        text = (out / "checks.txt").read_text(encoding="utf-8") if (out / "checks.txt").exists() else ""
        check("checks.txt copied verbatim", "verdict=ok" in text)
        check("checks.txt printed to stdout", "verdict=ok" in copied.stdout)
        check("boot.txt copied", (out / "boot.txt").exists())

        empty = work / "empty.img"
        empty_boot = work / "empty-boot"
        (empty_boot / "extlinux").mkdir(parents=True)
        (empty_boot / "dtbs").mkdir()
        (empty_boot / "KERNEL").write_bytes(b"\x01" * (2 * MIB))
        (empty_boot / "extlinux" / "extlinux.conf").write_text(
            "LABEL DEEPoS\nLINUX /KERNEL\nFDT /dtbs/rk3326-r36s-v20.dtb\n", encoding="utf-8")
        run(sys.executable, "tools/mkimage.py", "--out", str(empty),
            "--layout", "tests/fixtures/layout-small.json",
            "--size-mib", "80", "--boot", str(empty_boot),
            "--sys-a", str(work / "sys"), "--data", str(work / "data"))
        empty_target = work / "empty-target.img"
        empty_target.write_bytes(b"\x00" * empty.stat().st_size)
        run(sys.executable, "tools/dpflash.py", "--image", str(empty),
            "--target", str(empty_target), "--no-defer-table")
        nothing = run(sys.executable, "tools/read-report.py", "--target", str(empty_target))
        check("missing report is reported, not crashed",
              nothing.returncode != 0 and "missing" in (nothing.stdout + nothing.stderr))
    return finish()


def finish():
    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  report: {len(failed)} check(s) failed")
        return 1
    print("PASS  report: boot partition discovery, listing, copy, missing-report guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
