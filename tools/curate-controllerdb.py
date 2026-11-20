"""Trim PortMaster's SDL game controller database down to something the kernel accepts.

PortMaster's control.txt publishes the whole controller database through the
SDL_GAMECONTROLLERCONFIG environment variable:

    sdl_controllerconfig="$(< "${SDL_GAMECONTROLLERCONFIG_FILE}")"
    export SDL_GAMECONTROLLERCONFIG=...

The upstream file is about 470 KiB. Linux limits a single argv/env string to
MAX_ARG_STRLEN (32 pages = 128 KiB), so every execve() inside the port then
fails with E2BIG and the port dies with "Argument list too long" - the failure
mode DEEPoS hit on NFSU1 and FlatOut 2.

The fix keeps the handheld controllers people actually use, always appends the
R36S pad, and caps the result well below the limit.

Usage:
    python3 tools/curate-controllerdb.py <portmaster-dir>
        reads  <portmaster-dir>/PortMaster/gamecontrollerdb.txt
        writes <portmaster-dir>/PortMaster/gamecontrollerdb.txt   (curated)
               <portmaster-dir>/PortMaster/gamecontrollerdb.full.txt (original)
"""

import argparse
import pathlib
import re
import sys

# Families worth keeping on a 640x480 handheld: built-in pads, USB/DualSense pads
# and RetroArch's own "generic" fallbacks.
KEEP = re.compile(
    r"anbernic|r36s|retroid|gamepad|8bitdo|dualshock|dualsense|xbox|switch|stadia|"
    r"generic|powera|gamesir|legion|ayn|powkiddy|trimui|rg351|rg350|rg300|rg552|"
    r"odroid|pi400|steam|nvidia|shield|playstation|joystick",
    re.IGNORECASE,
)

# SDL derives this GUID from bus 0x19 (platform) plus the device name on the
# R36S-V20; it is stable across boots, unlike the USB gadget MAC.
R36S_GUID = "19003982723336735f47616d65706100"
R36S_LINE = (
    f"{R36S_GUID},r36s_Gamepad,"
    "a:b1,b:b0,x:b2,y:b3,"
    "back:b8,start:b9,"
    "leftshoulder:b4,rightshoulder:b5,"
    "leftstick:b11,rightstick:b12,"
    "dpup:b13,dpdown:b14,dpleft:b15,dpright:b16,"
    "leftx:a0,lefty:a1,rightx:a2,righty:a3,"
    "lefttrigger:b6,righttrigger:b7,"
    "platform:Linux,"
)

CAP = 110_000


def curate(lines, cap=CAP):
    kept, total = [], 0
    for line in lines:
        line = line.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) < 3 or not KEEP.search(fields[1]):
            continue
        if total + len(line) + 1 > cap:
            continue
        kept.append(line)
        total += len(line) + 1
    return kept, total


def main():
    ap = argparse.ArgumentParser(description="trim the PortMaster SDL controller database")
    ap.add_argument("portmaster", help="directory that contains PortMaster/")
    ap.add_argument("--cap", type=int, default=CAP, help=f"byte budget (default {CAP})")
    args = ap.parse_args()

    root = pathlib.Path(args.portmaster) / "PortMaster"
    db = root / "gamecontrollerdb.txt"
    full = root / "gamecontrollerdb.full.txt"
    if not db.is_file():
        sys.exit(f"missing {db}")
    original = db.read_bytes()
    if len(original) <= args.cap:
        print(f"controller db already small: {len(original)} bytes")
        return
    if not full.is_file():
        full.write_bytes(original)
    kept, total = curate(original.decode("utf-8", "replace").splitlines(), args.cap)
    body = "\n".join(kept + [R36S_LINE, ""])
    db.write_text(body, encoding="utf-8")
    print(
        f"controller db: {len(original)} -> {len(body)} bytes "
        f"({len(kept)} entries + r36s_Gamepad, budget {total})"
    )
    if len(body) > 128 * 1024:
        sys.exit("curated database still exceeds MAX_ARG_STRLEN")


if __name__ == "__main__":
    main()
