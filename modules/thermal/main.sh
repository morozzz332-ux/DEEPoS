#!/bin/bash
# DEEPoS thermal module: shows temperatures and switches CPU/GPU profiles.
#
# Transport: NDJSON JSON-RPC on stdin/stdout (see docs/FIRMWARE-SPEC.md §7).
# The module never writes to /sys: it drops a request file into its private data
# directory and the root helper (root/thermal-apply.sh, run by a .path unit)
# applies it. That keeps the module inside the sandbox.
set -u

SYSFS="${SYSFS_PREFIX:-}"
DATA="${MODD_MODULE_DATA:-${ARCHR_MODULE_DATA:-}}"
REQUEST="$DATA/request"
STATUS="$DATA/status"

zone() { # zone <type> -> millidegrees
    local f
    for f in "$SYSFS"/sys/class/thermal/thermal_zone*/type; do
        [ -r "$f" ] || continue
        if [ "$(cat "$f")" = "$1" ]; then
            cat "${f%type}temp" 2>/dev/null
            return 0
        fi
    done
    return 1
}

cpu_cur() { cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq" 2>/dev/null; }
cpu_max() { cat "$SYSFS/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq" 2>/dev/null; }
gpu_cur() { cat "$SYSFS/sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/cur_freq" 2>/dev/null; }

mode() { # current profile as the root helper last reported it
    sed -n 's/.*"mode":"\([a-z]*\)".*/\1/p' "$STATUS" 2>/dev/null | head -n1
}

emit() { printf '%s\n' "$1"; }

emit_updates() {
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"tile:temps\",\"value\":\"$(zone soc-thermal 2>/dev/null)\"}}"
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:soc\",\"value\":{\"key\":\"@val.temp\",\"args\":[\"soc\",\"$(zone soc-thermal 2>/dev/null)\"]}}}"
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:gpu\",\"value\":{\"key\":\"@val.temp\",\"args\":[\"gpu\",\"$(zone gpu-thermal 2>/dev/null)\"]}}}"
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:cpu\",\"value\":{\"key\":\"@val.cpu\",\"args\":[\"$(cpu_cur 2>/dev/null)\",\"$(cpu_max 2>/dev/null)\"]}}}"
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:gpuclock\",\"value\":\"$(gpu_cur 2>/dev/null)\"}}"
    emit "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:mode\",\"value\":\"$(mode 2>/dev/null)\"}}"
}

handle_action() { # handle_action <action>
    case "$1" in
        eco|balanced|max)
            [ -n "$DATA" ] || return 0
            mkdir -p "$DATA" 2>/dev/null
            printf '%s\n' "$1" > "$REQUEST"
            return 0
            ;;
    esac
    return 0
}

while IFS= read -r line; do
    [ -z "$line" ] && continue
    id=$(printf '%s' "$line" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([-0-9][0-9]*\).*/\1/p' | head -n1)
    method=$(printf '%s' "$line" | sed -n 's/.*"method"[[:space:]]*:[[:space:]]*"\([a-z._]*\)".*/\1/p' | head -n1)
    [ -z "$id" ] && continue

    case "$method" in
        initialize)
            emit "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"ready\":true}}"
            emit_updates
            ;;
        action.invoke)
            action=$(printf '%s' "$line" | sed -n 's/.*"action"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\1/p' | head -n1)
            handle_action "$action"
            emit "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"ok\":true,\"action\":\"$action\"}}"
            emit_updates
            ;;
        shutdown)
            emit "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{}}"
            exit 0
            ;;
        *)
            emit "{\"jsonrpc\":\"2.0\",\"id\":$id,\"error\":{\"message\":\"unknown method\"}}"
            ;;
    esac
done
