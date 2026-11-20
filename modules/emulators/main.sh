#!/bin/sh
# DEEPoS on-demand diagnostic module; replies on stdout in NDJSON.
inspect() {
    runtime=${DEEPOS_EMULATORS:-/data/emus}
    installed='отсутствует'
    [ ! -x "$runtime/retroarch" ] || installed='установлен'
    count=0
    for core in "$runtime"/cores/*_libretro.so; do
        [ ! -f "$core" ] || count=$((count + 1))
    done
    printf 'RetroArch: %s\\nЯдер RetroArch: %s' "$installed" "$count"
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
