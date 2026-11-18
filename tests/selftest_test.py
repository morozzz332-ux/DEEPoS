#!/usr/bin/env python3
"""--selftest prints the launcher environment; this checks the parsable contract."""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/w")
BIN = ROOT / "apps/launcher/launcher"


def run(args):
    return subprocess.run([str(BIN), *args], capture_output=True, text=True)


def kv(out):
    """collect every key=value pair, including several per line"""
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", out))


def main() -> int:
    if not BIN.exists():
        print("FAIL  selftest: launcher binary missing")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="selftest-"))
    roms = tmp / "roms"
    (roms / "md").mkdir(parents=True)
    for i in range(3):
        (roms / "md" / f"g{i}.md").write_text("rom", encoding="utf-8")
    (roms / "snes").mkdir()
    (roms / "snes" / "a.sfc").write_text("rom", encoding="utf-8")

    data = tmp / "data"
    data.mkdir()
    (data / "continue.tsv").write_text(
        "Sonic\tmega drive\t2 мин\t1\t1\tmd\tg0.md\n", encoding="utf-8")
    (data / "emulators.toml").write_text('md = "echo %ROM%"\n', encoding="utf-8")

    res = run(["--roms", str(roms), "--data", str(data),
               "--emulators", str(data / "emulators.toml"),
               "--modules-socket", str(tmp / "nope.sock"), "--selftest"])
    ok = True
    if res.returncode != 0:
        print(f"FAIL  selftest exit {res.returncode}: {res.stderr}")
        return 1
    got = kv(res.stdout)
    checks = [
        ("status", "ok"),
        ("systems", "2"),
        ("games", "4"),
        ("continue", "1"),
        ("emulators_present", "1"),
        ("modules", "0"),
    ]
    for key, want in checks:
        if got.get(key) != want:
            print(f"FAIL  selftest {key}={got.get(key)!r}, want {want!r}")
            ok = False
    if got.get("fb_present") not in ("0", "1"):
        print(f"FAIL  selftest fb_present={got.get('fb_present')!r}")
        ok = False
    if not got.get("input_events", "").isdigit():
        print(f"FAIL  selftest input_events={got.get('input_events')!r}")
        ok = False
    # settings file is reported with the values the UI will show
    cfg = tmp / "settings.toml"
    cfg.write_text("brightness = 40\nvolume = 55\nprofile = eco\n", encoding="utf-8")
    res = run(["--roms", str(roms), "--data", str(data), "--config", str(cfg),
               "--modules-socket", str(tmp / "nope.sock"), "--selftest"])
    got = kv(res.stdout)
    for key, want in (("brightness", "40"), ("volume", "55"), ("profile", "eco")):
        if got.get(key) != want:
            print(f"FAIL  selftest config {key}={got.get(key)!r}, want {want!r}")
            ok = False
    if got.get("config") != str(cfg):
        print(f"FAIL  selftest config path={got.get('config')!r}")
        ok = False

    for need in ("roms", "data", "emulators", "modd", "fb", "input_events", "version"):
        if need not in got:
            print(f"FAIL  selftest misses key {need}")
            ok = False

    # missing library must not crash: zero counts, still status=ok
    res = run(["--roms", str(tmp / "empty"), "--data", str(tmp / "nodata"), "--selftest"])
    got = kv(res.stdout)
    if res.returncode != 0 or not got.get("systems", "").lstrip("-").isdigit():
        print(f"FAIL  selftest on empty env: rc={res.returncode} {res.stderr}")
        ok = False
    if got.get("status") != "ok":
        print(f"FAIL  selftest empty env status={got.get('status')!r}")
        ok = False

    print("PASS  selftest: parses roms/continue/emulators/modd/fb and survives an empty device"
          if ok else "FAIL  selftest")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
