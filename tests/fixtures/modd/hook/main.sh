#!/bin/sh
# Fixture module: answers the launch hook and denies ROMs with "blocked" in the name.
while IFS= read -r line; do
    id=$(printf '%s' "$line" | sed -n 's/.*"id":[ ]*\([0-9]*\).*/\1/p')
    [ -n "$id" ] || continue
    case "$line" in
        *'"method":"initialize"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"ready":true}}\n' "$id" ;;
        *'"method":"launch.before"'*)
            case "$line" in
                *blocked*) printf '{"jsonrpc":"2.0","id":%s,"result":{"decision":"deny"}}\n' "$id" ;;
                *)         printf '{"jsonrpc":"2.0","id":%s,"result":{"decision":"allow"}}\n' "$id" ;;
            esac ;;
        *)
            printf '{"jsonrpc":"2.0","id":%s,"error":{"message":"unsupported"}}\n' "$id" ;;
    esac
done