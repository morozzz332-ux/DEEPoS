#!/bin/sh
# Pin the Mali GPU clock while a game runs.
#
# dArkOSRE wraps every launch in `perfmax ... perfnorm`: it raises the clocks
# before the emulator starts and restores them afterwards. DEEPoS already runs
# policy0 at "performance" all the time, so only the GPU is left: panfrost's
# simple_ondemand drops to the minimum between frames and every port stutters
# (and stutter is what the leftover audio crackle sounds like).
#
# Usage: perf-boost.sh on|off|state
set -u
gpu=/sys/class/devfreq/ff400000.gpu
gov=$gpu/governor
idle=simple_ondemand

case "${1:-}" in
on)
    [ -w "$gov" ] || exit 0
    echo performance > "$gov" 2>/dev/null || exit 0
    ;;
off)
    [ -w "$gov" ] || exit 0
    # Only put back the on-demand governor if we were the ones who changed it.
    [ "$(cat "$gov" 2>/dev/null)" = performance ] || exit 0
    echo "$idle" > "$gov" 2>/dev/null || true
    ;;
state)
    echo "governor=$(cat "$gov" 2>/dev/null || echo none)"
    echo "cur_freq=$(cat "$gpu/cur_freq" 2>/dev/null || echo none)"
    ;;
*)
    echo "usage: perf-boost.sh on|off|state" >&2
    exit 2
    ;;
esac
