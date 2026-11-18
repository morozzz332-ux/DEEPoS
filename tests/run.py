#!/usr/bin/env python3
"""DEEPoS launcher test suite (host-side, no device required).

Builds the launcher, renders every screen into PPM via the CLI, then checks
layout invariants, palette usage, determinism and golden hashes.

Usage:
    python tests/run.py            # run all checks
    python tests/run.py --update   # refresh tests/golden/hashes.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "apps" / "launcher" / "launcher"
GOLDEN = ROOT / "tests" / "golden" / "hashes.json"
SCREENS = ["continue", "systems", "games", "settings", "modules", "files", "info"]
W, H = 640, 480

PALETTE = {
    (0x0C, 0x10, 0x0E), (0x13, 0x1A, 0x16), (0x18, 0x22, 0x1C), (0x20, 0x2A, 0x24),
    (0xE9, 0xED, 0xE7), (0x98, 0xA6, 0x9D), (0x5F, 0x6D, 0x65), (0x79, 0xD8, 0x9A),
    (0x18, 0x24, 0x1D), (0xE6, 0xB2, 0x5C), (0xE0, 0x70, 0x6A),
}

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def build() -> None:
    subprocess.run(["make", "-C", str(ROOT / "apps" / "launcher"), "-s"], check=True)


def fixture_tree(base: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    roms = base / "roms"
    data = base / "data"
    layout = {"md": 312, "snes": 286, "psx": 110, "gba": 204, "psp": 48,
              "dc": 36, "n64": 52, "gb": 167, "gbc": 153, "nes": 198,
              "arcade": 241, "sms": 94}
    for system, count in layout.items():
        d = roms / system
        d.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (d / f"game{i:03d}.bin").write_bytes(b"\0" * 16)
    data.mkdir(parents=True, exist_ok=True)
    (data / "continue.tsv").write_text(
        "Sonic 3 & Knuckles\tmega drive\t12 мин\t2\t1\n"
        "Crash Bandicoot 2\tplaystation\t1 ч 04\t0\t0\n"
        "Lumines\tpsp\t46 мин\t0\t1\n"
        "Streets of Rage 2\tmega drive\tвчера\t0\t0\n"
        "Mario Kart 64\tnintendo 64\tвчера\t0\t0\n",
        encoding="utf-8")
    return roms, data


def render(roms: pathlib.Path, data: pathlib.Path, screen: str,
           out: pathlib.Path) -> bytes:
    subprocess.run([str(LAUNCHER), "--roms", str(roms), "--data", str(data),
                    "--screen", screen, "--out", str(out),
                    "--clock", "14:32", "--battery", "78",
                    "--rom-used", "12592", "--rom-total", "36864"],
                   check=True)
    return out.read_bytes()


def parse_ppm(raw: bytes) -> tuple[int, int, list[tuple[int, int, int]]]:
    header, _, rest = raw.partition(b"\n")
    check(header == b"P6", f"ppm header is {header!r}, expected b'P6'")
    dims, _, rest = rest.partition(b"\n")
    maxval, _, body = rest.partition(b"\n")
    check(maxval.strip() == b"255", f"ppm maxval is {maxval!r}, expected b'255'")
    parts = dims.split()
    check(len(parts) == 2, f"ppm dims malformed: {dims!r}")
    w, h = int(parts[0]), int(parts[1])
    check(len(body) >= w * h * 3, "ppm payload shorter than expected")
    px = [(body[i], body[i + 1], body[i + 2]) for i in range(0, w * h * 3, 3)]
    return w, h, px


def ink_rows(px: list[tuple[int, int, int]], w: int, y0: int, y1: int) -> int:
    rows = 0
    for y in range(y0, y1):
        lit = any(px[y * w + x] != PALETTE_BG for x in range(w))
        rows += 1 if lit else 0
    return rows


PALETTE_BG = (0x0C & 0xF8, 0x10 & 0xFC, 0x0E & 0xF8)


def palette565() -> set[tuple[int, int, int]]:
    """Colours the launcher may emit: theme tokens truncated to RGB565."""
    theme = (ROOT / "apps" / "launcher" / "src" / "dp_theme.h").read_text("utf-8")
    allowed = set()
    pattern = r"dp565\(\s*0x([0-9A-Fa-f]{2})\s*,\s*0x([0-9A-Fa-f]{2})\s*,\s*0x([0-9A-Fa-f]{2})\s*\)"
    for r, g, b in re.findall(pattern, theme):
        allowed.add((int(r, 16) & 0xF8, int(g, 16) & 0xFC, int(b, 16) & 0xF8))
    return allowed


PALETTE565 = palette565()


def run_tests(update: bool) -> None:
    hashes: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        roms, data = fixture_tree(base)
        for screen in SCREENS:
            out = base / f"{screen}.ppm"
            raw = render(roms, data, screen, out)
            digest = hashlib.sha256(raw).hexdigest()

            again = render(roms, data, screen, base / f"{screen}.2.ppm")
            check(hashlib.sha256(again).hexdigest() == digest,
                  f"{screen}: render is not deterministic")

            w, h, px = parse_ppm(raw)
            check((w, h) == (W, H), f"{screen}: size {w}x{h} != {W}x{H}")
            unknown = {c for c in set(px) if c not in PALETTE565}
            check(len(unknown) == 0,
                  f"{screen}: {len(unknown)} colour(s) outside palette: "
                  f"{sorted(unknown)[:4]}")

            body_rows = ink_rows(px, w, 30, 454)
            check(body_rows >= 100, f"{screen}: body looks empty ({body_rows} rows)")
            status_rows = ink_rows(px, w, 0, 30)
            check(status_rows >= 18, f"{screen}: status bar looks empty")
            hashes[screen] = digest

        listing = subprocess.run(
            [str(LAUNCHER), "--roms", str(roms), "--list-roms"],
            check=True, capture_output=True, text=True).stdout
        check("md\t312" in listing, "--list-roms: md count 312 missing")
        check("snes\t286" in listing, "--list-roms: snes count 286 missing")
        check(listing.count("\n") >= 13, "--list-roms: expected >= 13 lines")

        screens = subprocess.run([str(LAUNCHER), "--list"], check=True,
                                 capture_output=True, text=True).stdout.split()
        check(screens == SCREENS, f"--list: screens {screens} != {SCREENS}")

        help_run = subprocess.run([str(LAUNCHER), "--help"],
                                  capture_output=True, text=True)
        check(help_run.returncode == 0, "--help: non-zero exit")
        check("--screen" in help_run.stdout, "--help: usage missing")

        bad = subprocess.run([str(LAUNCHER), "--roms", str(roms),
                              "--screen", "nope"],
                             capture_output=True, text=True)
        check(bad.returncode != 0, "unknown --screen must fail")

    if update:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
        print(f"golden updated: {GOLDEN.relative_to(ROOT)}")
        return

    if not GOLDEN.exists():
        failures.append(f"golden file missing: {GOLDEN.relative_to(ROOT)} "
                        "(run with --update)")
        return
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for screen, digest in hashes.items():
        want = expected.get(screen)
        check(want == digest,
              f"{screen}: pixels changed vs golden (run --update if intended)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    if not args.no_build:
        build()
    if not LAUNCHER.exists():
        failures.append(f"launcher binary not found: {LAUNCHER}")

    if not failures:
        run_tests(args.update)

    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print(f"PASS  screens={len(SCREENS)}  determinism=ok  palette=ok  golden=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
