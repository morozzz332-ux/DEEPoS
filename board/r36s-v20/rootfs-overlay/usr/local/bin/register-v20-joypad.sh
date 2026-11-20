#!/bin/sh
# devtmpfs and mdev create the node; RetroArch's evdev driver also needs the
# libudev joystick property. Publish it for the built-in pad once at boot.
set -eu

input=${1:-/sys/class/input}
database=${2:-/run/udev/data}
for event in "$input"/event*; do
    [ -r "$event/device/name" ] || continue
    IFS= read -r name < "$event/device/name" || continue
    [ "$name" = r36s_Gamepad ] || continue
    IFS= read -r phys < "$event/device/phys" || continue
    [ "$phys" = archr-singleadc-joypad/input0 ] || continue
    IFS= read -r number < "$event/dev" || continue
    record="$database/c$number"
    [ ! -e "$record" ] || exit 0
    mkdir -p "$database"
    # Preserve the real manager's record if it appeared since the check.
    ( umask 022; set -C; printf 'E:ID_INPUT=1\nE:ID_INPUT_JOYSTICK=1\n' > "$record" ) ||
        [ -e "$record" ]
    exit 0
done
