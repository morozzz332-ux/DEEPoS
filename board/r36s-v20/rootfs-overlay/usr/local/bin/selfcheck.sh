#!/bin/sh
# One-screen verdict for the first boot: what is present, what is missing.
# Output format is stable (key=value) so the PC-side reader can diff it.
set -u
OUT=${1:-/flash/report/checks.txt}
tmp="$OUT.tmp.$$"

kernel=$(uname -r 2>/dev/null)

panel=absent
for s in /sys/class/drm/*/status; do
    [ -r "$s" ] || continue
    if [ "$(cat "$s" 2>/dev/null)" = "connected" ]; then panel=present; break; fi
done

input_events=0
for e in /dev/input/event*; do [ -e "$e" ] && input_events=$((input_events + 1)); done

battery=absent
for b in /sys/class/power_supply/*; do
    [ -r "$b/type" ] || continue
    case "$(cat "$b/type" 2>/dev/null)" in
        Battery) battery=present; break ;;
    esac
done

charger=absent
for b in /sys/class/power_supply/*; do
    [ -r "$b/type" ] || continue
    case "$(cat "$b/type" 2>/dev/null)" in
        Mains|USB) charger=present; break ;;
    esac
done

is_mounted() { grep -qs " $1 " /proc/mounts; }
data=absent;  is_mounted /data  && data=$( [ -w /data ] && echo rw || echo ro )
roms=absent;  is_mounted /storage && roms=mounted
flash=absent; is_mounted /flash && flash=rw
modd=stopped; pgrep -x modd >/dev/null 2>&1 && modd=running
launcher=absent
if [ "${2:-}" = "--first-frame" ] || pgrep -x launcher >/dev/null 2>&1; then
    launcher=running
fi

zram=absent; zram_active=0
[ -e /sys/block/zram0/disksize ] && zram=present
swaptotal=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null)
[ "${swaptotal:-0}" -gt 0 ] 2>/dev/null && zram_active=1

mem_total=$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo 2>/dev/null)
mem_avail=$(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo 2>/dev/null)

soc=unknown
for z in /sys/class/thermal/thermal_zone*; do
    [ -r "$z/temp" ] || continue
    case "$(cat "$z/type" 2>/dev/null)" in
        soc-thermal) soc=$(( $(cat "$z/temp") / 1000 )) ;;
    esac
done

verdict=PASS
[ "$panel" = present ] || verdict=FAIL
[ "$data" = rw ] || verdict=FAIL

{
    echo "kernel=$kernel"
    echo "verdict=$verdict"
    echo "panel=$panel"
    echo "input_events=$input_events"
    echo "battery=$battery"
    echo "charger=$charger"
    echo "flash=$flash"
    echo "data=$data"
    echo "roms=$roms"
    echo "modd=$modd"
    echo "launcher=$launcher"
    echo "zram=$zram"
    echo "swap_active=$zram_active"
    echo "mem_total_mb=$mem_total"
    echo "mem_available_mb=$mem_avail"
    echo "soc_c=$soc"
} 2>/dev/null > "$tmp" && mv -f "$tmp" "$OUT" || {
    rm -f "$tmp"
    exit 1
}

cat "$OUT" 2>/dev/null
exit 0
