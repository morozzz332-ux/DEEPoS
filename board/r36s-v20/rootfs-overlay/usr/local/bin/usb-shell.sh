#!/bin/sh
# DEEPoS USB debug entry (port).
# Launched by the launcher: Ports -> "usb-shell". Returns control at once and
# leaves on the USB network: a root shell on :23 (nc/telnetd) and a file
# server on :8080 with a live snapshot (/storage/report/live.txt).
set -u

rep=/storage/report
mkdir -p "$rep" 2>/dev/null || true
log="$rep/usb-shell.log"
: > "$log" 2>&1 || true

say() { echo "$*" >> "$log" 2>&1; }

# port_ok <hex-port>: is something listening on that port?
# Listeners may live in /proc/net/tcp (IPv4) or /proc/net/tcp6 (busybox binds ::).
port_ok() {
    for f in /proc/net/tcp /proc/net/tcp6; do
        [ -r "$f" ] || continue
        awk -v want=":${1}" 'NR > 1 && index($2, want) > 0 && $4 == "0A" { found = 1 } END { exit !found }' "$f" 2>/dev/null && return 0
    done
    return 1
}

snapshot() {
    snap="$rep/live.txt"
    {
        echo "=== identity ==="
        date 2>/dev/null
        uname -a 2>/dev/null
        cat /proc/cmdline 2>/dev/null
        cat /etc/os-release 2>/dev/null
        echo "=== uptime ==="
        cat /proc/uptime 2>/dev/null
        echo "=== memory ==="
        head -n 6 /proc/meminfo 2>/dev/null
        cat /proc/pressure/memory 2>/dev/null
        echo "=== temps ==="
        for z in /sys/class/thermal/thermal_zone*; do
            [ -r "$z/temp" ] || continue
            echo "$(cat "$z/type" 2>/dev/null)=$(( $(cat "$z/temp" 2>/dev/null) / 1000 ))C"
        done
        echo "=== cpu ==="
        for c in /sys/devices/system/cpu/cpufreq/policy*; do
            [ -d "$c" ] || continue
            echo "$(basename "$c") cur=$(cat "$c/scaling_cur_freq" 2>/dev/null) max=$(cat "$c/scaling_max_freq" 2>/dev/null) gov=$(cat "$c/scaling_governor" 2>/dev/null)"
        done
        echo "profile=$(cat /data/cpu-profile 2>/dev/null)"
        echo "=== battery ==="
        cat /sys/class/power_supply/battery/status 2>/dev/null
        cat /sys/class/power_supply/battery/capacity 2>/dev/null
        echo "=== disk ==="
        df -h 2>/dev/null
        echo "=== usb ==="
        cat /run/deepos-usb.mode 2>/dev/null
        cat /run/deepos-usb.address 2>/dev/null
        echo "=== selfcheck ==="
        cat /flash/report/selftest.txt 2>/dev/null
        tail -n 5 /flash/report/checks.txt 2>/dev/null
    } > "$snap" 2>&1 || true
}

say "date=$(date 2>/dev/null)"
say "uname=$(uname -a 2>/dev/null)"
say "mode=$(cat /run/deepos-usb.mode 2>/dev/null)"
say "iface=$(cat /run/deepos-usb.iface 2>/dev/null)"
say "addr=$(cat /run/deepos-usb.address 2>/dev/null)"

snapshot
say "snapshot=$rep/live.txt"

# Single-shot busybox nc in a loop: every disconnect re-opens the listener.
( while :; do nc -l -p 23 -e /bin/sh; sleep 1; done ) >/dev/null 2>&1 &
sleep 1
say "listen23_after_nc=$(port_ok 0017 && echo yes || echo no)"

if ! port_ok 0017; then
    telnetd -l /bin/sh -p 23 >/dev/null 2>&1 &
    sleep 1
    say "listen23_after_telnetd=$(port_ok 0017 && echo yes || echo no)"
fi

# Independent second channel: plain HTTP file server with the snapshot.
httpd -p 8080 -h "$rep" >/dev/null 2>&1 &
sleep 1
say "listen8080=$(port_ok 1F90 && echo yes || echo no)"

# Keep the snapshot reasonably fresh while the port is active.
( while :; do sleep 30; snapshot; done ) >/dev/null 2>&1 &

status="shell=$(port_ok 0017 && echo ready || echo none) http=$(port_ok 1F90 && echo yes || echo no)"
echo "$status" > "$rep/usb-shell.status"
say "status=$status"
