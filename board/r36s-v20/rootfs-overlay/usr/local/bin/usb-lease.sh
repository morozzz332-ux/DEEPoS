#!/bin/sh
# Apply a lease only to the currently selected dedicated USB network interface.
state=/run/deepos-usb
[ "${interface:-}" = "$(cat "$state.iface" 2>/dev/null)" ] && [ -n "$interface" ] || exit 0
valid_ipv4() {
    case "$1" in ''|*[!0-9.]*) return 1 ;; esac
}

case "$1" in
    deconfig)
        ip -4 addr flush dev "$interface"
        rm -f "$state.address" /run/deepos-usb-resolv.conf
        ;;
    bound|renew)
        valid_ipv4 "${ip:-}" && valid_ipv4 "${subnet:-}" || exit 1
        ifconfig "$interface" "$ip" netmask "$subnet" up || exit 1
        ip -4 route del default dev "$interface" metric 512 2>/dev/null || true
        for gateway in ${router:-}; do
            valid_ipv4 "$gateway" || continue
            ip -4 route add default via "$gateway" dev "$interface" metric 512 && break
        done
        {
            for server in ${dns:-}; do
                valid_ipv4 "$server" && printf 'nameserver %s\n' "$server"
            done
        } > /run/deepos-usb-resolv.conf
        printf '%s\n' "$ip" > "$state.address"
        ;;
esac
