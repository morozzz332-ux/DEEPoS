#!/usr/bin/env python3
"""Rebuild the board DTB with the speaker routed to the codec class-D stage.

The stock V20 tree offers two sound cards and neither plays the speaker:

* ``rk817-sound-simple`` routes ``Internal Speakers`` to ``SPKO``; DAPM then
  powers SPKO but never powers ``Enable Class D`` (R64 bit 0x80) or
  ``Class D Mode`` (R56 bit 0x10), so the class-D output stays muted.
* ``rk817-sound-amplified`` wires an external ``simple-audio-amplifier`` fed
  from HPOL/HPOR; the enable line rises, but the speaker stays silent because
  the class-D stage is bypassed.

Routing the speaker pin to the ``SPK DAC`` widget instead pulls the class-D
supply chain in: on the console this turned a silent 660 Hz tone into audible
output with everything else untouched.

Run inside the boot-repair image (it carries dtc)::

    docker run --rm -v "$PWD:/w" -w /w deepos-build:boot-repair \
        sh -c 'python3 tools/dtb-sound-fix.py build/stock.dtb \
            board/r36s-v20/boot/dtbs/rk3326-r36s-v20.dtb'

The output is committed, so a normal build only needs the file that already
lives in ``board/r36s-v20/boot/dtbs``.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

OLD_ROUTE = "Internal Speakers\0SPKO"
NEW_ROUTE = "Internal Speakers\0SPK DAC"


def decompile(dtb, dts):
    subprocess.run(["dtc", "-I", "dtb", "-O", "dts", "-o", str(dts), str(dtb)],
                   check=True, stderr=subprocess.DEVNULL)


def compile_dts(dts, dtb):
    subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(dts)],
                   check=True, stderr=subprocess.DEVNULL)


def patch(dts):
    text = dts.read_text(encoding="utf-8")
    # dtc escapes NUL separators as \0 inside the string list.
    escaped_old = OLD_ROUTE.replace("\0", "\\0")
    escaped_new = NEW_ROUTE.replace("\0", "\\0")
    if escaped_old not in text:
        if escaped_new in text:
            return False
        raise SystemExit("speaker route not found in the device tree")
    if text.count(escaped_old) != 1:
        raise SystemExit("speaker route appears more than once")
    dts.write_text(text.replace(escaped_old, escaped_new), encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", help="stock board dtb")
    ap.add_argument("output", help="patched dtb to write")
    args = ap.parse_args()

    source = pathlib.Path(args.source)
    output = pathlib.Path(args.output)
    if not source.is_file():
        raise SystemExit("missing source dtb: %s" % source)

    with tempfile.TemporaryDirectory() as tmp:
        dts = pathlib.Path(tmp) / "board.dts"
        decompile(source, dts)
        changed = patch(dts)
        if changed:
            compile_dts(dts, output)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, output)

    blob = output.read_bytes()
    if NEW_ROUTE.encode() not in blob:
        raise SystemExit("patched dtb lost the SPK DAC route")
    print("%s: %s (%d bytes)" % (output, "patched" if changed else "already patched",
                                 len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
