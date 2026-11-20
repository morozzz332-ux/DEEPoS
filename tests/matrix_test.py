#!/usr/bin/env python3
"""V20 acceptance matrix: the 175-row registry and its rendered report.

Run inside the build image:  python3 tests/matrix_test.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "v20_matrix.py"
DATA = ROOT / "board" / "r36s-v20" / "data"
SYSTEMS = DATA / "systems.tsv"
EVIDENCE = DATA / "matrix-evidence.tsv"
CHECKS = [
    "core_load", "stand", "menu", "video", "audio", "controls", "sticks",
    "volume", "fn_save", "exit", "sram", "exit_state", "resume", "reboot",
    "recovery", "performance",
]

checks = 0
failures = []


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{name}{': ' + detail if detail else ''}")


def sh(*args):
    return subprocess.run(
        [sys.executable, str(TOOL), "--root", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def rows():
    out = []
    for line in SYSTEMS.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        out.append(line.split("\t"))
    return out


def main():
    check("registry exists", SYSTEMS.exists(), str(SYSTEMS))
    if not SYSTEMS.exists():
        return report()

    res = sh("--check")
    check("registry check passes", res.returncode == 0,
          (res.stdout + res.stderr).strip())

    data = rows()
    check("registry has 175 systems", len(data) == 175, str(len(data)))
    check("every row has 10 columns", all(len(r) == 10 for r in data))
    ids = [r[0] for r in data]
    check("systems are unique", len(ids) == len(set(ids)))
    check("bios is not a system", "bios" not in ids)
    check("ports is a system", "ports" in ids)

    visible = {r[0] for r in data if r[3] == "yes"}
    folders = {
        line.strip()
        for line in (DATA / "rom-folders.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    check("every rom folder is in the registry", (folders - {"bios"}) <= visible,
          ", ".join(sorted((folders - {"bios"}) - visible)))
    check("visible rows match rom-folders", len(visible) == len(folders - {"bios"}))

    routed = [r for r in data if r[4] != "none"]
    check("most systems have a route", len(routed) >= 140, str(len(routed)))
    for row in data:
        if row[4] == "retroarch":
            check(f"{row[0]} has a core", bool(row[5]))
        if row[4] == "none":
            check(f"{row[0]} without route has no source", row[8] == "none",
                  f"source={row[8]}")
        if row[4] == "port":
            check(f"{row[0]} port route", row[0] == "ports")
    aliases = {r[0]: r[9] for r in data if r[9]}
    check("alias rows exist", len(aliases) >= 10, str(len(aliases)))
    for entry, base in aliases.items():
        check(f"alias {entry} points to a system", base in ids, base)

    bios_rows = {r[0] for r in data if r[7]}
    check("saturn needs BIOS", "saturn" in bios_rows)
    check("psx BIOS is listed", "psx" in bios_rows)
    check("segacd BIOS is listed", "segacd" in bios_rows)

    # Evidence must never invent a system or a check.
    if EVIDENCE.exists():
        for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            check("evidence has 4 columns", len(parts) == 4, line)
            check(f"evidence system {parts[0]} is registered", parts[0] in ids)
            check(f"evidence check {parts[1]} is known", parts[1] in CHECKS)

    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "matrix.md"
        res = sh("--write", str(out))
        check("render succeeds", res.returncode == 0, (res.stdout + res.stderr).strip())
        text = out.read_text(encoding="utf-8") if out.exists() else ""
        check("render names the registry size", "**175**" in text)
        check("render lists every system", text.count("| `") >= 175)
        check("render marks invisible systems", "**нет**" in text)
        check("render has no python repr", "None" not in text)

    return report()


def report():
    if failures:
        print(f"matrix_test: {checks} checks, {len(failures)} FAIL")
        for item in failures:
            print(f"  FAIL {item}")
        return 1
    print(f"matrix_test: {checks} checks, 0 FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
