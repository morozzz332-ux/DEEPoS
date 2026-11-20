#!/bin/sh
# DEEPoS USB gadget: CDC-ACM serial console + a network link on the OTG port.
#
# Why: the handheld has no sshd and the UART pads need a soldering iron. With this
# script the same USB cable gives a COM port (when the kernel has the ACM
# function) and a network interface (169.254.170.2/16) for quick checks.
#
# Everything the kernel refuses is recorded in /flash/report/usb.txt, because the
# only way to read that on the PC is the very link this script tries to bring up.
set -u

GADGET_DIR=/sys/kernel/config/usb_gadget/deepos
UDC_DIR=/sys/class/udc
REPORT=/flash/report/usb.txt

log() { echo "usb-gadget: $*"; }

report() {
    log "$*"
    { [ -d /flash/report ] || mkdir -p /flash/report 2>/dev/null; } || true
    echo "usb-gadget: $*" >>"$REPORT" 2>/dev/null || true
}

[ -d /sys/kernel/config ] || { report "fail: no /sys/kernel/config"; exit 0; }
mount -t configfs none /sys/kernel/config 2>/dev/null || true
[ -d /sys/kernel/config/usb_gadget ] ||
    { report "fail: no configfs gadget support"; exit 1; }
[ -d "$UDC_DIR" ] || { report "fail: no UDC (host mode?)"; exit 1; }

udc=$(ls "$UDC_DIR" 2>/dev/null | head -n 1)
[ -n "$udc" ] || { report "fail: no UDC available"; exit 1; }
report "udc=$udc state=$(cat "$UDC_DIR/$udc/state" 2>/dev/null)"

mkdir -p "$GADGET_DIR" 2>/dev/null || true
cd "$GADGET_DIR" || exit 1

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "deepos-0001" > strings/0x409/serialnumber
echo "DEEPoS" > strings/0x409/manufacturer
echo "DEEPoS debug gadget" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "acm+net" > configs/c.1/strings/0x409/configuration

if mkdir -p functions/acm.gs0 2>/dev/null; then
    report "acm=ok"
else
    report "acm=missing"
fi

net_fn=""
if mkdir -p functions/ncm.usb0 2>/dev/null; then
    net_fn=ncm.usb0
    report "ncm=ok"
else
    report "ncm=missing"
fi
if [ -z "$net_fn" ] && mkdir -p functions/rndis.usb0 2>/dev/null; then
    net_fn=rndis.usb0
    report "rndis=ok"
fi
[ -n "$net_fn" ] || report "fail: no network function"

[ -e "configs/c.1/acm.gs0" ] ||
    ln -s functions/acm.gs0 configs/c.1/ 2>/dev/null || true
[ -n "$net_fn" ] && {
    [ -e "configs/c.1/$net_fn" ] ||
        ln -s "functions/$net_fn" configs/c.1/ 2>/dev/null || true
}

if [ -z "$(cat UDC 2>/dev/null)" ]; then
    if echo "$udc" >UDC 2>/dev/null; then
        report "bound=$udc"
    else
        report "fail: cannot bind UDC $udc"
        exit 1
    fi
fi

# Give the network side a fixed link-local address; the PC side gets 169.254.170.1.
i=0
while [ $i -lt 20 ]; do
    if [ -d /sys/class/net/usb0 ]; then
        ip link set usb0 up 2>/dev/null || true
        ip addr add 169.254.170.2/16 dev usb0 2>/dev/null || true
        report "usb0 state=$(cat /sys/class/net/usb0/operstate 2>/dev/null) \
speed=$(cat /sys/class/net/usb0/speed 2>/dev/null) net=$net_fn"
        exit 0
    fi
    i=$((i + 1))
    sleep 1
done
report "fail: usb0 did not appear (net=$net_fn)"
exit 0
