#!/bin/sh
# DEEPoS USB gadget: CDC-ACM serial console + NCM network, both on the OTG port.
#
# Why: the handheld has no sshd and the UART pads need a soldering iron. With this
# script the same USB cable gives a COM port (interactive root shell through getty)
# and a network interface (169.254.170.2/16) for quick checks.
set -u

GADGET_DIR=/sys/kernel/config/usb_gadget/deepos
UDC_DIR=/sys/class/udc

log() { echo "usb-gadget: $*"; }

[ -d /sys/kernel/config ] || exit 0
mount -t configfs none /sys/kernel/config 2>/dev/null || true
[ -d /sys/kernel/config/usb_gadget ] || { log "no configfs gadget support"; exit 1; }
[ -d "$UDC_DIR" ] || { log "no UDC (not in peripheral mode)"; exit 1; }

udc=$(ls "$UDC_DIR" 2>/dev/null | head -n 1)
[ -n "$udc" ] || { log "no UDC available"; exit 1; }

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
echo "acm+ncm" > configs/c.1/strings/0x409/configuration

mkdir -p functions/acm.gs0
mkdir -p functions/ncm.usb0

[ -e configs/c.1/acm.gs0 ] || ln -s functions/acm.gs0 configs/c.1/ 2>/dev/null || true
[ -e configs/c.1/ncm.usb0 ] || ln -s functions/ncm.usb0 configs/c.1/ 2>/dev/null || true

if [ -z "$(cat UDC 2>/dev/null)" ]; then
    echo "$udc" > UDC 2>/dev/null || { log "cannot bind UDC $udc"; exit 1; }
fi
log "bound to $udc"

# Give the network side a fixed link-local address; the PC side gets 169.254.170.1.
i=0
while [ $i -lt 20 ]; do
    if [ -d /sys/class/net/usb0 ]; then
        ip link set usb0 up 2>/dev/null || true
        ip addr add 169.254.170.2/16 dev usb0 2>/dev/null || true
        log "usb0 up with 169.254.170.2/16"
        break
    fi
    i=$((i + 1))
    sleep 1
done

exit 0
