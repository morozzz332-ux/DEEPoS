#!/usr/bin/env python3
"""The demo "game" that proves the launch chain.

playdemo is what the launcher starts through emulators.toml. On the host it
writes the frame into a file instead of /dev/fb0, so the same binary and the
same code path can be checked without the console.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "apps/playdemo/playdemo"
failures = []


def check(name, ok, detail=""):
    if ok:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def run(fb, keys=None, rom=None, extra=()):
    cmd = [str(BIN), "--fb", str(fb)]
    if keys:
        cmd += ["--keys", keys]
    if rom:
        cmd.append(rom)
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True)


def ink(path):
    data = path.read_bytes()
    return sum(1 for b in data if b)


def main():
    with tempfile.TemporaryDirectory() as name:
        tmp = pathlib.Path(name)
        fb = tmp / "frame.bin"

        p = run(fb, keys="DOWN,A,DOWN,B", rom="/storage/ports/demo.sh", extra=["--exit-after", "4"])
        check("demo runs with synthetic keys", p.returncode == 0, p.stderr.strip()[:200])
        check("demo reports the rom it was given", "rom=/storage/ports/demo.sh" in p.stdout,
              p.stdout.strip()[:200])
        check("frame is 640x480x16", fb.is_file() and fb.stat().st_size == 640 * 480 * 2,
              str(fb.stat().st_size if fb.exists() else "missing"))
        check("frame has pixels", ink(fb) > 1000)

        p = run(fb, keys="UP,UP", rom="/storage/ports/demo.sh", extra=["--exit-after", "2"])
        check("UP presses are counted", "presses=2" in p.stdout, p.stdout.strip()[:200])

        p = run(fb, keys="B", rom="/storage/ports/demo.sh", extra=["--exit-after", "1"])
        check("B exits immediately", "done=1" in p.stdout)

        p = run(tmp / "nested" / "missing.bin", keys="A", rom="x.md")
        check("missing display path fails cleanly",
              p.returncode != 0 and "no display" in (p.stderr or ""),
              (p.stderr or "").strip()[:200])

    if failures:
        print(f"\nFAIL  playdemo: {len(failures)} problem(s)")
        return 1
    print("PASS  playdemo: frame, keys, rom argument and display errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
