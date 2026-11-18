#!/bin/sh
# DEEPoS thermal helper - runs as root from a .path unit when the module asks
# for a profile switch. Reads <data>/request, applies it, writes <data>/status.
#
# SYSFS_PREFIX exists only for host tests: on the device it is empty and the
# helper talks to the real /sys tree.
set -eu

DATA="${1:?usage: thermal-apply.sh <module-data-dir>}"
SYSFS="${SYSFS_PREFIX:-}"
PROFILE_FILE="${PROFILE_FILE:-/storage/cpu-profile}"
APPLY="${APPLY:-/usr/local/bin/cpu-profile.sh}"

[ -r "$DATA/request" ] || exit 0
mode=$(sed -n '1s/[[:space:]]*$//p' "$DATA/request")
case "$mode" in
    eco|balanced|max) ;;
    *) rm -f "$DATA/request"; exit 2 ;;
esac

mkdir -p "$DATA"
[ -n "${PROFILE_FILE%/*}" ] && mkdir -p "$(dirname "$PROFILE_FILE")" 2>/dev/null || true
printf '%s\n' "$mode" > "$PROFILE_FILE"

if [ -x "$APPLY" ]; then
    "$APPLY" "$mode" >/dev/null 2>&1 || true
fi

cpu_max=$(cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq" 2>/dev/null || echo 0)
gov=$(cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_governor" 2>/dev/null || echo unknown)
gpu_max=$(cat "$SYSFS/sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/max_freq" 2>/dev/null || echo 0)
ts=$(date +%s)

printf '{"mode":"%s","governor":"%s","cpu_max_khz":%s,"gpu_max_hz":%s,"ts":%s}\n' \
    "$mode" "$gov" "$cpu_max" "$gpu_max" "$ts" > "$DATA/status.tmp"
mv "$DATA/status.tmp" "$DATA/status"
chmod 644 "$DATA/status" 2>/dev/null || true
rm -f "$DATA/request"
