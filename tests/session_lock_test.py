#!/usr/bin/env python3
"""Stage test: one game session at a time (launch lock)."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "apps" / "launcher" / "launcher"
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def main() -> int:
    print("session lock: second launch, stale lock, release")
    if not BIN.exists():
        print(f"  FAIL launcher binary missing: {BIN}")
        return 1
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="deepos-lock-"))
    data = tmp / "data"
    roms = tmp / "roms"
    (roms / "md").mkdir(parents=True)
    (roms / "md" / "g0.md").write_text("rom")
    data.mkdir()

    slow = tmp / "slow.sh"
    slow.write_text("#!/bin/sh\nsleep 2\n")
    quick = tmp / "quick.sh"
    quick.write_text("#!/bin/sh\nexit 0\n")
    slow_emu = tmp / "slow.toml"
    slow_emu.write_text(f'md = "/bin/sh {slow} %ROM%"\n')
    quick_emu = tmp / "quick.toml"
    quick_emu.write_text(f'md = "/bin/sh {quick} %ROM%"\n')

    base = [str(BIN), "--data", str(data), "--roms", str(roms), "--run-game", "md:g0.md"]
    first = subprocess.Popen(base + ["--emulators", str(slow_emu)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lock = data / "launch.lock"
    seen = False
    for _ in range(60):
        if lock.exists():
            seen = True
            break
        time.sleep(0.05)
    check("lock file is taken while a session runs", seen)

    second = subprocess.run(base + ["--emulators", str(slow_emu)],
                            capture_output=True, text=True, timeout=15)
    check("second launch is refused with code 7", second.returncode == 7,
          f"rc={second.returncode}")
    check("refusal names the running session",
          "another game session" in second.stderr, second.stderr.strip())

    first_rc = first.wait(timeout=15)
    check("first session still finishes normally", first_rc == 0, f"rc={first_rc}")
    check("lock is released after the session", not lock.exists())

    # A pid that no longer exists must not keep the menu locked forever.
    lock.write_text("999999\n")
    stale = subprocess.run(base + ["--emulators", str(quick_emu)],
                           capture_output=True, text=True, timeout=15)
    check("stale lock is replaced", stale.returncode == 0, f"rc={stale.returncode}")
    check("stale lock is gone after the session", not lock.exists())

    if failures:
        print(f"FAIL  session lock: {len(failures)} problem(s)")
        return 1
    print("PASS  session lock: second launch, stale lock, release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
