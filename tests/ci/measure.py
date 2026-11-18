#!/usr/bin/env python3
"""Measure launcher artefacts, render timings and test timings inside the build image.

The numbers land in docs/metrics.md; the goal is to notice regressions early,
not to micro-benchmark the container.
"""
import pathlib
import subprocess
import tempfile
import time

ROOT = pathlib.Path("/w")
LAUNCHER = ROOT / "apps/launcher/launcher"
GOLDEN = ROOT / "tests/golden/hashes.json"
SCREENS = ["continue", "systems", "games", "settings", "modules", "files", "info"]

print(f"launcher_bytes={LAUNCHER.stat().st_size}")
print(f"golden_bytes={GOLDEN.stat().st_size}")

tmp = pathlib.Path(tempfile.mkdtemp(prefix="measure-"))
roms = tmp / "roms"
(roms / "md").mkdir(parents=True)
for i in range(64):
    (roms / "md" / f"g{i}.md").write_text("rom", encoding="utf-8")
data = tmp / "data"
data.mkdir()

for screen in SCREENS:
    best = None
    for _ in range(5):
        out = tmp / "frame.ppm"
        start = time.monotonic()
        subprocess.run([str(LAUNCHER), "--roms", str(roms), "--data", str(data),
                        "--screen", screen, "--out", str(out)],
                       check=True, capture_output=True)
        ms = (time.monotonic() - start) * 1000
        best = ms if best is None else min(best, ms)
    print(f"screen_ms_{screen}={best:.1f}")

start = time.monotonic()
subprocess.run(["python3", "tests/run.py", "--no-build"], cwd=ROOT,
               check=True, capture_output=True)
print(f"test_ms={int((time.monotonic() - start) * 1000)}")

start = time.monotonic()
subprocess.run(["sh", "tests/ci/render-all.sh", "/w", "/w/tests/out"], cwd=ROOT,
               check=True, capture_output=True)
print(f"render_ms={int((time.monotonic() - start) * 1000)}")
