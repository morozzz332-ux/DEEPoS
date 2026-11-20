#!/bin/sh
# DEEPoS on-demand diagnostic module; replies on stdout in NDJSON.
report_volume() {
    if awk -v path="$2" '$2 == path { found=1 } END {exit !found}' /proc/mounts; then
        df -m "$2" | awk -v label="$1" 'NR==2 {
            printf "%s: %d из %d МиБ свободно", label, $4, $2
        }'
    else
        printf '%s: раздел недоступен' "$1"
    fi
}

inspect() {
    report_volume DATA /data
    printf '\\n'
    report_volume ROMS /storage
    printf '\\n'
    report_volume TF2 /games
}

while IFS= read -r request; do
    id=$(printf '%s\n' "$request" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p')
    [ -n "$id" ] || continue
    case "$request" in
        *'"method":"initialize"'*)
            printf '{"id":%s,"result":{"ready":true}}\n' "$id" ;;
        *'"method":"action.invoke"'*'"action":"inspect"'*)
            printf '{"id":%s,"result":{"message":"%s"}}\n' "$id" "$(inspect)" ;;
        *)
            printf '{"id":%s,"error":{"message":"unsupported method or action"}}\n' "$id" ;;
    esac
done
