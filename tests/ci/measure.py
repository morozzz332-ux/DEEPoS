#!/usr/bin/env python3
"""Measure launcher artefacts and test timings inside the build image."""
import pathlib
import subprocess
import time

ROOT = pathlib.Path("/w")
launcher = ROOT / "apps/launcher/launcher"
golden = ROOT / "tests/golden/hashes.json"

print(f"launcher_bytes={launcher.stat().st_size}")
print(f"golden_bytes={golden.stat().st_size}")

start = time.monotonic()
subprocess.run(["python3", "tests/run.py", "--no-build"], cwd=ROOT,
               check=True, capture_output=True)
print(f"test_ms={int((time.monotonic() - start) * 1000)}")

start = time.monotonic()
subprocess.run(["sh", "tests/ci/render-all.sh", "/w", "/w/tests/out"], cwd=ROOT,
               check=True, capture_output=True)
print(f"render_ms={int((time.monotonic() - start) * 1000)}")
