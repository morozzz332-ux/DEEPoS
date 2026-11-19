#!/usr/bin/env python3
"""DEEPoS launcher input tests: synthetic keys drive the same state machine that
evdev drives on the device, so navigation is testable without any hardware."""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "apps" / "launcher" / "launcher"

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


def make_library(base: pathlib.Path):
    roms = base / "roms"
    data = base / "data"
    for sys_id, count in (("md", 5), ("snes", 3)):
        d = roms / sys_id
        d.mkdir(parents=True)
        for i in range(count):
            (d / f"g{i}.{ 'md' if sys_id == 'md' else 'sfc'}").write_bytes(b"")
    data.mkdir(parents=True)
    (data / "continue.tsv").write_text(
        "Sonic 3 & Knuckles\tMEGA DRIVE\t12 мин\t2\t1\n"
        "Crash Bandicoot 2\tPLAYSTATION\t1 ч 04\t-1\t0\n"
        "Lumines\tPSP\t46 мин\t0\t1\n",
        encoding="utf-8",
    )
    return roms, data


def state(roms, data, keys=""):
    cmd = [str(BIN), "--roms", str(roms), "--data", str(data)]
    if keys:
        cmd += ["--keys", keys]
    cmd += ["--print-state"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p, p.stdout.strip()


def main():
    if not BIN.exists():
        print(f"FAIL  build launcher first: {BIN} is missing")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        source = ROOT / "apps/launcher/src"
        helper = tmp / "input-evdev"
        subprocess.run(["cc", "-std=c11", "-D_GNU_SOURCE", "-I", str(source),
                        str(source / "dp_input.c"), str(ROOT / "tests/fixtures/input_evdev.c"),
                        "-Wl,--wrap=open,--wrap=ioctl", "-o", str(helper)], check=True)
        evdev = subprocess.run([str(helper)], capture_output=True, text=True)
        check("evdev accepts the V20 D-pad and physical A/B layout", evdev.returncode == 0,
              evdev.stderr.strip())
        roms, data = make_library(tmp)

        p, out = state(roms, data)
        check("default state is the continue list", out == "screen=continue level=0 sel=0 system=0", out)
        check("default run exits cleanly", p.returncode == 0, p.returncode)

        _, out = state(roms, data, "DOWN")
        check("DOWN moves the cursor", out.endswith("sel=1 system=0"), out)

        _, out = state(roms, data, "DOWN,DOWN,UP")
        check("UP moves the cursor back", out.endswith("sel=1 system=0"), out)

        _, out = state(roms, data, "DOWN,DOWN,DOWN,DOWN,DOWN")
        check("cursor stops at the last entry", out.endswith("sel=2 system=0"), out)

        _, out = state(roms, data, "UP")
        check("UP on the first entry stays put", out.endswith("sel=0 system=0"), out)

        _, out = state(roms, data, "RIGHT")
        check("RIGHT opens the system list", out.startswith("screen=systems"), out)

        _, out = state(roms, data, "RIGHT,A")
        check("A opens the game list", out == "screen=games level=1 sel=0 system=0", out)

        _, out = state(roms, data, "RIGHT,DOWN,A")
        check("A opens the highlighted system", out == "screen=games level=1 sel=0 system=1", out)

        _, out = state(roms, data, "RIGHT,DOWN,A,B")
        check("B returns to the system list", out == "screen=systems level=0 sel=1 system=1", out)

        _, out = state(roms, data, "RIGHT,DOWN,A,DOWN,DOWN")
        check("game list cursor follows system size", out.endswith("sel=2 system=1"), out)

        _, out = state(roms, data, "RIGHT,RIGHT")
        check("RIGHT cycles to settings", out.startswith("screen=settings"), out)

        _, out = state(roms, data, "LEFT")
        check("LEFT wraps to the last tab", out.startswith("screen=info"), out)

        _, out = state(roms, data, "LEFT,RIGHT")
        check("RIGHT from the last tab wraps to continue", out.startswith("screen=continue"), out)

        p, out = state(roms, data, "SPACE")
        check("unknown key is rejected", p.returncode == 2 and "unknown key" in (p.stderr or ""),
              (p.returncode, (p.stderr or "").strip()[:60]))

        p, out = state(roms, data, "RIGHT,A,B,quit")
        check("QUIT acknowledges and exits", p.returncode == 0, out)

        out_ppm = pathlib.Path(tmp) / "frame.ppm"
        p = subprocess.run(
            [str(BIN), "--roms", str(roms), "--data", str(data), "--keys", "RIGHT,RIGHT",
             "--out", str(out_ppm)],
            capture_output=True, text=True)
        data_ppm = out_ppm.read_bytes() if out_ppm.exists() else b""
        check("keys also drive the rendered frame",
              p.returncode == 0 and data_ppm.startswith(b"P6\n") and len(data_ppm) > 640 * 480 * 3,
              (p.returncode, len(data_ppm)))

    print("FAILED: " + ", ".join(FAILED) if FAILED else
          "PASS  input: key names, cursor, tabs, system/game navigation, quit, render")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
