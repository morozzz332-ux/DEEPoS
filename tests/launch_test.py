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

        nested = roms / "roms" / "GBA"
        nested.mkdir(parents=True)
        game = nested / "game with spaces.gba"
        game.write_text("rom")
        with emu.open("a") as config:
            config.write(f'gba = "sh {stub} %ROM%"\n')
        res = run_launcher(["--roms", str(roms), "--emulators", str(emu),
                            "--run-game", f"gba:{game.name}"])
        check(res.returncode == 0 and marker.read_text().splitlines() == [str(game)],
              f"nested Arch-R library forwards the original path: {res.stderr}")

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


        # 7. Continue screen: A on a saved row launches with its slot
        data_dir = tmp / "data"
        data_dir.mkdir()
        (data_dir / "continue.tsv").write_text(
            "Sonic 3 & Knuckles\tmega drive\t12 мин\t2\t1\tmd\tg0.md\n"
            "Crash Bandicoot 2\tplaystation\t1 ч 04\t-1\t0\tpsx\tg1.cue\n",
            encoding="utf-8",
        )
        marker.unlink(missing_ok=True)
        emu_slot.write_text(f'md = "sh {stub} %ROM% %SLOT%"\n')
        res = run_launcher(["--roms", str(roms), "--data", str(data_dir),
                            "--emulators", str(emu_slot), "--keys", "A"])
        check(res.returncode == 0, f"continue launch exit {res.returncode}: {res.stderr}")
        argv = marker.read_text() if marker.exists() else ""
        check(str(roms / "md" / "g0.md") in argv, f"continue launched wrong rom: {argv!r}")
        check("2" in argv.split(), f"continue slot not passed: {argv!r}")
        check("slot=2" in res.stdout, f"stdout: {res.stdout!r}")

        rom = roms / "md" / "A Hero's Quest.md"
        rom.write_text("rom")
        marker.unlink(missing_ok=True)
        screen = run_launcher(["--roms", str(roms), "--data", str(data_dir),
                               "--emulators", str(emu_slot), "--screen", "games",
                               "--keys", "A"])
        argv = marker.read_text().splitlines() if marker.exists() else []
        check(screen.returncode == 0 and argv[:1] == [str(rom)],
              f"game list A did not launch the selected file: {argv!r}")

        # 9. After a successful launch the Continue list is updated (atomically)
        upd = tmp / "data-upd"
        upd.mkdir()
        (upd / "continue.tsv").write_text(
            "Crash Bandicoot 2\tplaystation\tвчера\t1\t1\tpsx\tg1.cue\n",
            encoding="utf-8")
        res = run_launcher(["--roms", str(roms), "--data", str(upd),
                            "--emulators", str(emu_slot),
                            "--run-game", "md:g0.md", "--save-slot", "2"])
        check(res.returncode == 0, f"continue update launch failed: {res.stderr}")
        rows = (upd / "continue.tsv").read_text(encoding="utf-8").splitlines()
        check(bool(rows), "continue.tsv not written")
        cols = rows[0].split("\t")
        check(len(cols) == 7, f"first row has {len(cols)} columns: {rows[0]!r}")
        check(cols[5] == "md" and cols[6] == "g0.md", f"first row rom wrong: {rows[0]!r}")
        check(cols[3] == "2" and cols[4] == "1", f"slot/has_save wrong: {rows[0]!r}")
        check(any("psx" in r for r in rows[1:]), "previous row was dropped")
        check(not (upd / "continue.tsv.tmp").exists(), "temporary file left behind")

        # 10. Repeat launch must not duplicate the row
        run_launcher(["--roms", str(roms), "--data", str(upd),
                      "--emulators", str(emu_slot),
                      "--run-game", "md:g0.md", "--save-slot", "1"])
        rows = (upd / "continue.tsv").read_text(encoding="utf-8").splitlines()
        same = [r for r in rows if r.split("\t")[5:7] == ["md", "g0.md"]]
        check(len(same) == 1, f"duplicate rows: {rows}")
        check(same[0].split("\t")[3] == "1", f"slot not updated: {same[0]!r}")

        # 8. Continue row without a rom (older continue.tsv) must not launch
        (data_dir / "continue.tsv").write_text(
            "Sonic 3 & Knuckles\tmega drive\t12 мин\t2\t1\n", encoding="utf-8")
        marker.unlink(missing_ok=True)
        res = run_launcher(["--roms", str(roms), "--data", str(data_dir),
                            "--emulators", str(emu_slot), "--keys", "A", "--print-state"])
        check(res.returncode == 0, f"no-rom continue exit {res.returncode}")
        check(not marker.exists(), "continue row without rom must not launch")

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
    print("PASS  launch: emulators.toml, %ROM%/%SLOT%, hook, continue screen, continue.tsv update, exit codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
