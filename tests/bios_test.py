#!/usr/bin/env python3
"""Check the manifest and no-overwrite behavior of the open BIOS installer."""
from pathlib import Path
import runpy
import tempfile

ROOT = Path(__file__).resolve().parents[1]
install = runpy.run_path(str(ROOT / "tools/install-open-bios.py"))["install"]

with tempfile.TemporaryDirectory() as scratch:
    volume = Path(scratch)
    expected = len((ROOT / "bios/manifest.tsv").read_text().splitlines()) - 1
    assert install(volume) == (expected, 0, 0)
    assert install(volume) == (0, expected, 0)
    original = volume / "bios/tos.img"
    original.write_bytes(b"user-owned BIOS")
    assert install(volume) == (0, expected - 1, 1)
    assert original.read_bytes() == b"user-owned BIOS"
print("PASS  open BIOS: checksums, repeated install, existing BIOS preserved")
