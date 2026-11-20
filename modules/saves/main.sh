#!/bin/sh
# DEEPoS saves module: shows the last backup and asks the root helper for a new one.
#
# Same sandbox rule as the thermal module: the module only writes a request file,
# the root helper (root/saves-backup.sh) does the tar.
set -u

DATA="${MODD_MODULE_DATA:-${ARCHR_MODULE_DATA:-}}"
REQUEST="$DATA/request"
STATUS="$DATA/status"

field() { # field <name> -> value from the helper's status JSON
    sed -n "s/.*\"$1\":\([^,}]*\).*/\1/p" "$STATUS" 2>/dev/null | head -n1 | tr -d '"'
}

last_ts() { field ts; }
last_files() { field files; }

emit_updates() {
    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"tile:saves\",\"value\":\"$(last_ts)\"}}"
    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:last\",\"value\":\"$(last_ts)\"}}"
    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"method\":\"ui.update\",\"params\":{\"target\":\"row:count\",\"value\":\"$(last_files)\"}}"
}

while IFS= read -r line; do
    [ -z "$line" ] && continue
    id=$(printf '%s' "$line" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([-0-9][0-9]*\).*/\1/p' | head -n1)
    method=$(printf '%s' "$line" | sed -n 's/.*"method"[[:space:]]*:[[:space:]]*"\([a-z._]*\)".*/\1/p' | head -n1)
    [ -z "$id" ] && continue

    case "$method" in
        initialize)
            printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"ready\":true}}"
            emit_updates
            ;;
        action.invoke)
            action=$(printf '%s' "$line" | sed -n 's/.*"action"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\1/p' | head -n1)
            if [ "$action" = "backup" ] && [ -n "$DATA" ]; then
                if ! mkdir -p "$DATA" || ! printf 'backup\n' > "$REQUEST"; then
                    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"error\":{\"message\":\"cannot persist request\"}}"
                    continue
                fi
            fi
            printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"ok\":true,\"action\":\"$action\"}}"
            emit_updates
            ;;
        shutdown)
            printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{}}"
            exit 0
            ;;
        *)
            printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"error\":{\"message\":\"unknown method\"}}"
            ;;
    esac
done
