#!/bin/sh
# DEEPoS on-demand diagnostic module; replies on stdout in NDJSON.
inspect() {
    for supply in "${SYSFS_PREFIX:-}"/sys/class/power_supply/*; do
        [ -r "$supply/capacity" ] || continue
        IFS= read -r charge < "$supply/capacity" || continue
        case "$charge" in ''|*[!0-9]*) continue ;; esac
        state=Неизвестно
        if [ -r "$supply/status" ]; then
            IFS= read -r status < "$supply/status" || status=
            case "$status" in
                Charging) state='Заряжается' ;;
                Discharging) state='Разряжается' ;;
                Full) state='Заряжена' ;;
                'Not charging') state='Не заряжается' ;;
            esac
        fi
        printf 'Заряд: %s%% · %s' "$charge" "$state"
        return
    done
    printf '%s' 'Датчик заряда недоступен.'
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
