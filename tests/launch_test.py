"""Tests for the launcher -> modd -> emulator launch pipeline (host only).

The emulator is a stub shell script that records its argv, so the whole path
(module hook decision, emulators.toml lookup, %ROM% expansion, child exit code)
is verified without a handheld.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "apps" / "launcher" / "launcher"
MODD = ROOT / "apps" / "modd" / "modd"
FIXTURES = ROOT / "tests" / "fixtures" / "modd"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def run_launcher(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)
    return subprocess.run(
        [str(LAUNCHER), *args],
        capture_output=True,
        text=True,
        env=proc_env,
        timeout=30,
    )


def start_modd(tmp: pathlib.Path) -> tuple[subprocess.Popen, pathlib.Path]:
    sock = tmp / "modd.sock"
    env = dict(os.environ)
    env["MODD_INIT_MS"] = "800"
    env["MODD_ACTION_MS"] = "600"
    proc = subprocess.Popen(
        [str(MODD), "--modules", str(FIXTURES), "--socket", str(sock),
         "--data", str(tmp / "data")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    for _ in range(100):
        if sock.exists():
            break
        if proc.poll() is not None:
            raise RuntimeError("modd exited early: " + proc.stderr.read().decode())
        import time

        time.sleep(0.05)
    return proc, sock


def main() -> int:
    check(LAUNCHER.exists(), f"launcher missing: {LAUNCHER}")
    check(MODD.exists(), f"modd missing: {MODD}")
    if not LAUNCHER.exists() or not MODD.exists():
        print("FAIL")
        for f in failures:
            print("  -", f)
        return 1

    with tempfile.TemporaryDirectory() as raw:
        tmp = pathlib.Path(raw)
        roms = tmp / "roms"
        (roms / "md").mkdir(parents=True)
        (roms / "md" / "g0.md").write_text("rom")
        (roms / "md" / "blocked.md").write_text("rom")

        stub = tmp / "stub.sh"
        marker = tmp / "argv.txt"
        stub.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" > {marker}\n"
            "exit ${STUB_RC:-0}\n"
        )
        stub.chmod(0o755)

        emu = tmp / "emulators.toml"
        emu.write_text(f'md = "sh {stub} %ROM%"\n')

        # 1. happy path: emulator receives the rom path
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                            "--run-game", "md:g0.md"])
        check(res.returncode == 0, f"run-game exit {res.returncode}: {res.stderr}")
        check(marker.exists(), "emulator stub did not run")
        check(marker.exists() and str(roms / "md" / "g0.md") in marker.read_text(),
              "emulator did not get the rom path")
        check("launch\tmd\tg0.md\tslot=-1\t0" in res.stdout, f"stdout: {res.stdout!r}")

        # 2. unknown system -> code 5
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                            "--run-game", "snes:g0.sfc"])
        check(res.returncode == 5, f"unknown system exit {res.returncode}")

        # 3. malformed argument -> code 2
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                            "--run-game", "g0.md"])
        check(res.returncode == 2, f"missing ':' exit {res.returncode}")

        # 4. failing emulator -> launcher reports failure
        marker.unlink(missing_ok=True)
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                            "--run-game", "md:g0.md"], {"STUB_RC": "3"})
        check(res.returncode == 1, f"child failure exit {res.returncode}")
        check("launch\tmd\tg0.md\tslot=-1\t3" in res.stdout, f"stdout: {res.stdout!r}")


        # 6. save slot is passed to the emulator (%SLOT%)
        emu_slot = tmp / "emulators-slot.toml"
        emu_slot.write_text(f'md = "sh {stub} %ROM% %SLOT%"\n')
        marker.unlink(missing_ok=True)
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu_slot),
                            "--save-slot", "3", "--run-game", "md:g0.md"])
        check(res.returncode == 0, f"slot exit {res.returncode}: {res.stderr}")
        argv = marker.read_text() if marker.exists() else ""
        check(str(roms / "md" / "g0.md") in argv and "3" in argv.split(),
              f"slot not passed: {argv!r}")
        check("slot=3" in res.stdout, f"stdout: {res.stdout!r}")

        # 5. module hook: allow and deny through a real modd
        proc, sock = start_modd(tmp)
        try:
            marker.unlink(missing_ok=True)
            res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                                "--modules-socket", str(sock),
                                "--run-game", "md:g0.md"])
            check(res.returncode == 0, f"hook allow exit {res.returncode}: {res.stderr}")
            check(marker.exists(), "hook allow did not reach the emulator")

            marker.unlink(missing_ok=True)
            res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                                "--modules-socket", str(sock),
                                "--run-game", "md:blocked.md"])
            check(res.returncode == 4, f"hook deny exit {res.returncode}")
            check("blocked\tmd\tblocked.md" in res.stdout, f"stdout: {res.stdout!r}")
            check(not marker.exists(), "denied game must not reach the emulator")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS  launch: emulators.toml, %ROM%/%SLOT% expansion, hook allow/deny, exit codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
