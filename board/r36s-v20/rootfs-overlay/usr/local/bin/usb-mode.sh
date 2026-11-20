#!/bin/sh
# Switch the V20 OTG port between local networking and exclusive ROMS export.
set -u

mode=${1:-}
case "$mode" in off|network|files) ;; *) exit 2 ;; esac
root=/sys/kernel/config
gadget=$root/usb_gadget/deepos-transfer
state=/run/deepos-usb
lun=$gadget/functions/mass_storage.roms/lun.0
storage=/storage

exec 9>/run/deepos-usb.lock
flock -n 9 || exit 1

roms=$(cat /run/deepos-roms-device 2>/dev/null)
case "$roms" in /dev/mmcblk[0-9]p5) ;; *) roms= ;; esac
udc_state() {
    controller=$(cat "$gadget/UDC" 2>/dev/null)
    [ -z "$controller" ] || cat "/sys/class/udc/$controller/state" 2>/dev/null
}

finish() {
    if [ -r "$state.pid" ]; then
        read -r pid < "$state.pid"
        rm -f "$state.iface" "$state.pid" "$state.address" /run/deepos-usb-resolv.conf
        case "$pid" in
            ''|*[!0-9]*) ;;
            *) if [ "$(cat "/proc/$pid/comm" 2>/dev/null)" = udhcpc ]; then
                   kill "$pid" 2>/dev/null || true
               fi ;;
        esac
    fi
    if [ -n "$(cat "$gadget/UDC" 2>/dev/null)" ]; then
        printf '\n' > "$gadget/UDC" || return 1
    fi
    if [ -n "$(cat "$lun/file" 2>/dev/null)" ]; then
        printf '\n' > "$lun/file" || return 1
    fi
    for name in ncm.usb0 rndis.usb0 mass_storage.roms; do
        if [ -L "$gadget/configs/c.1/$name" ]; then
            rm "$gadget/configs/c.1/$name" || return 1
        fi
    done
    if [ -f "$state.export" ]; then
        [ -b "$roms" ] || return 1
        if ! grep -q "^$roms $storage " /proc/mounts; then
            mount -o noatime "$roms" "$storage" || return 1
        fi
        rm -f "$state.export"
    fi
    rm -f "$state.mode"
    if [ -r "$state.role" ]; then
        read -r role old < "$state.role"
        case "$role:$old" in
            /sys/class/usb_role/*ff300000*/role:host|/sys/class/usb_role/*ff300000*/role:none)
                printf '%s\n' "$old" > "$role" || return 1 ;;
        esac
        rm -f "$state.role"
    fi
}

# A configured host must eject the LUN before the console takes it back.
if [ -n "$(cat "$lun/file" 2>/dev/null)" ] && [ "$(udc_state)" = configured ]; then
    exit 4
fi
finish || exit 1
[ "$mode" != off ] || exit 0

failed() { finish; exit "${1:-1}"; }
for role in /sys/class/usb_role/*ff300000*/role; do
    [ -r "$role" ] || continue
    old=$(cat "$role")
    if [ "$old" != device ]; then
        printf '%s %s\n' "$role" "$old" > "$state.role" || exit 1
        printf 'device\n' > "$role" || failed
    fi
    break
done

controller=
for delay in 1 2 3 4 5 6 7 8 9 10; do
    for candidate in /sys/class/udc/*ff300000*; do
        [ -e "$candidate" ] && controller=${candidate##*/} && break
    done
    [ -z "$controller" ] || break
    sleep 0.1
done
[ -n "$controller" ] || failed 3
mount -t configfs none "$root" 2>/dev/null || true
[ -d "$root/usb_gadget" ] || failed
mkdir -p "$gadget/strings/0x409" "$gadget/configs/c.1/strings/0x409" || failed
printf '0x1d6b\n' > "$gadget/idVendor" || failed
printf 'DEEPoS\n' > "$gadget/strings/0x409/manufacturer" || failed
printf 'DEEPoS USB\n' > "$gadget/strings/0x409/product" || failed
printf '%s\n' "$mode" > "$gadget/configs/c.1/strings/0x409/configuration" || failed

if [ "$mode" = files ]; then
    [ -b "$roms" ] && grep -q "^$roms $storage " /proc/mounts || failed 6
    mkdir -p "$gadget/functions/mass_storage.roms" || failed 5
    printf '0x0100\n' > "$gadget/idProduct" || failed
    printf '1\n' > "$lun/removable" || failed
    printf '0\n' > "$lun/ro" || failed
    : > "$state.export" || failed
    umount "$storage" || failed 6
    devno=$(cat "/sys/class/block/${roms##*/}/dev" 2>/dev/null) || failed
    if awk -v dev="$devno" '$3==dev { found=1 } END { exit !found }' /proc/self/mountinfo; then
        failed 6
    fi
    printf '%s\n' "$roms" > "$lun/file" || failed
    function=mass_storage.roms
else
    printf '0x0104\n' > "$gadget/idProduct" || failed
    function=ncm.usb0
    if ! mkdir -p "$gadget/functions/$function" 2>/dev/null; then
        function=rndis.usb0
        mkdir -p "$gadget/functions/$function" || failed 7
    fi
fi
ln -s "$gadget/functions/$function" "$gadget/configs/c.1/$function" || failed
printf '%s\n' "$controller" > "$gadget/UDC" || failed
if [ "$mode" = network ]; then
    iface=$(cat "$gadget/functions/$function/ifname" 2>/dev/null)
    iface=${iface:-usb0}
    ip link set "$iface" up || failed
    printf '%s\n' "$iface" > "$state.iface" || failed
    udhcpc -f -i "$iface" -s /usr/local/bin/usb-lease.sh 9>&- </dev/null >/dev/null 2>&1 &
    pid=$!
    if ! printf '%s\n' "$pid" > "$state.pid"; then
        kill "$pid" 2>/dev/null || true
        failed
    fi
fi
printf '%s\n' "$mode" > "$state.mode" || failed
