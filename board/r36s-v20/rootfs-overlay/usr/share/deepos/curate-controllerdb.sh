#!/bin/sh
# Keep PortMaster's SDL controller database usable on this kernel.
#
# control.txt publishes the whole database through one environment variable:
#     sdl_controllerconfig="$(< "${SDL_GAMECONTROLLERCONFIG_FILE}")"
#     export SDL_GAMECONTROLLERCONFIG=...
# Linux caps a single argv/env string at MAX_ARG_STRLEN (32 pages = 128 KiB).
# The upstream file is ~470 KiB, so every execve() inside the port failed with
# E2BIG and the port died with "Argument list too long". The build trims the
# bundled copy, but a PortMaster update restores the full file, so the trim is
# repeated on every port start.
#
# Usage: curate-controllerdb.sh [<portmaster-data-dir>] [<byte-budget>]
set -eu

porthome=${1:-/data/portmaster}
budget=${2:-110000}
db=$porthome/PortMaster/gamecontrollerdb.txt
full=$porthome/PortMaster/gamecontrollerdb.full.txt

# SDL derives this GUID from bus 0x19 plus the device name, so it is stable
# across boots (unlike the USB gadget MAC). A and B are swapped on purpose:
# the RetroArch autoconfig puts A on button 1 on this handheld.
r36s='19003982723336735f47616d65706100,r36s_Gamepad,a:b1,b:b0,x:b2,y:b3,back:b8,start:b9,leftshoulder:b4,rightshoulder:b5,leftstick:b11,rightstick:b12,dpup:b13,dpdown:b14,dpleft:b15,dpright:b16,leftx:a0,lefty:a1,rightx:a2,righty:a3,lefttrigger:b6,righttrigger:b7,platform:Linux,'

[ -r "$db" ] || exit 0

if [ "$(wc -c < "$db")" -gt 120000 ]; then
    [ -f "$full" ] || cp "$db" "$full"
    tmp=$porthome/PortMaster/.gamecontrollerdb.new
    awk -F, -v budget="$budget" -v r36s="$r36s" '
        /^#/ || NF < 3 { next }
        tolower($2) !~ /anbernic|r36s|retroid|gamepad|8bitdo|dualshock|dualsense|xbox|switch|stadia|generic|powera|gamesir|legion|ayn|powkiddy|trimui|rg351|rg350|rg300|rg552|odroid|pi400|steam|nvidia|shield|playstation|joystick/ { next }
        total + length($0) + 1 > budget { next }
        { print; total += length($0) + 1 }
        END { print r36s }
    ' "$db" > "$tmp"
    mv -f "$tmp" "$db"
fi

# The bundled database may also predate the R36S entry.
if ! grep -q '^19003982723336735f47616d65706100,' "$db"; then
    printf '%s\n' "$r36s" >> "$db"
fi
