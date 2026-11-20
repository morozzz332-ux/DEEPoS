#!/bin/sh
# DEEPoS test module: completes initialize and records every action.
set -eu

data="${MODD_MODULE_DATA:-/tmp}"
: > "$data/actions.log"

while IFS= read -r line; do
    id=$(printf '%s' "$line" | sed -n 's/.*"id":\([0-9][0-9]*\).*/\1/p')
    [ -n "$id" ] || continue
    case "$line" in
    *'"method":"initialize"'*)
        printf 'ready\n' > "$data/state"
        printf '{"jsonrpc":"2.0","id":%s,"result":{"ready":true}}\n' "$id"
        ;;
    *'"method":"action.invoke"'*)
        act=$(printf '%s' "$line" | sed -n 's/.*"action":"\([a-z]*\)".*/\1/p')
        printf '%s\n' "${act:-none}" >> "$data/actions.log"
        printf '{"jsonrpc":"2.0","id":%s,"result":{"action":"%s"}}\n' "$id" "${act:-none}"
        ;;
    *)
        printf '{"jsonrpc":"2.0","id":%s,"result":{}}\n' "$id"
        ;;
    esac
done
