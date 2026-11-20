#!/bin/sh
# DEEPoS thermal helper - the root half of the thermal module. The module
# sandbox only writes <data>/request; this helper applies the CPU profile with
# the same owner the launcher settings card uses, so the module and the card can
# never disagree about the real limit.
#
# SYSFS_PREFIX exists only for host tests: there it points at a fixture root
# that contains sys/... . On the device it is empty and the helper talks to the
# real /sys tree. LAUNCHER/DATA_ROOT exist for tests and alternate installs.
set -eu

DATA="${1:?usage: thermal-apply.sh <module-data-dir>}"
SYSFS="${SYSFS_PREFIX:-}"
DATA_ROOT="${DATA_ROOT:-/data}"
PROFILE_FILE="${PROFILE_FILE:-/storage/cpu-profile}"
LAUNCHER="${LAUNCHER:-/usr/bin/launcher}"
APPLY="${APPLY:-/usr/local/bin/cpu-profile.sh}"

[ -r "$DATA/request" ] || exit 0
mode=$(sed -n '1s/[[:space:]]*$//p' "$DATA/request")
case "$mode" in
    eco|balanced|max) ;;
    *) rm -f "$DATA/request"; exit 2 ;;
esac

mkdir -p "$DATA" "$DATA_ROOT/config"
[ -n "${PROFILE_FILE%/*}" ] && mkdir -p "$(dirname "$PROFILE_FILE")" 2>/dev/null || true
printf '%s\n' "$mode" > "$PROFILE_FILE"

result="legacy"
reason=""
detail=""
if [ -x "$LAUNCHER" ]; then
    if [ -n "$SYSFS" ]; then
        out=$("$LAUNCHER" --data "$DATA_ROOT" --config "$DATA_ROOT/config/settings.toml" \
                          --sysfs "$SYSFS/sys" --set-power "$mode" 2>/dev/null || true)
    else
        out=$("$LAUNCHER" --data "$DATA_ROOT" --config "$DATA_ROOT/config/settings.toml" \
                          --set-power "$mode" 2>/dev/null || true)
    fi
    result=$(printf '%s\n' "$out" | awk -F'\t' '$1 == "power" { print $2; exit }')
    reason=$(printf '%s\n' "$out" | awk -F'\t' '$1 == "power" { print $3; exit }')
    detail=$(printf '%s\n' "$out" | awk -F'\t' '$1 == "power" { print $4; exit }')
    [ -n "$result" ] || result="error"
    [ -n "$reason" ] || reason="launcher did not report power"
elif [ -x "$APPLY" ]; then
    "$APPLY" "$mode" >/dev/null 2>&1 || true
fi

cpu_max=$(printf '%s' "$detail" | sed -n 's/.*cpu=[0-9-]*\.\.\([0-9][0-9]*\).*/\1/p')
[ -n "$cpu_max" ] || cpu_max=$(cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq" 2>/dev/null || echo 0)
gov=$(printf '%s' "$detail" | sed -n 's/.*governor=\([^ ]*\).*/\1/p')
case "$gov" in
    ""|-|unknown) gov=$(cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_governor" 2>/dev/null || echo unknown) ;;
esac
gpu_max=$(cat "$SYSFS/sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/max_freq" 2>/dev/null || echo 0)
ts=$(date +%s)

printf '{"mode":"%s","result":"%s","reason":"%s","governor":"%s","cpu_max_khz":%s,"gpu_max_hz":%s,"ts":%s}\n' \
    "$mode" "$result" "$reason" "$gov" "$cpu_max" "$gpu_max" "$ts" > "$DATA/status.tmp"
mv "$DATA/status.tmp" "$DATA/status"
chmod 644 "$DATA/status" 2>/dev/null || true
rm -f "$DATA/request"
