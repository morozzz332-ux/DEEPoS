#!/bin/sh
# Wait for the USB gadget serial node, then hand it to a login shell.
# Started from /etc/inittab with ::respawn, so a dropped console comes back.
i=0
while [ ! -e /dev/ttyGS0 ]; do
    i=$((i + 1))
    [ $i -gt 600 ] && exit 0
    sleep 3
done
exec /sbin/getty -L /dev/ttyGS0 115200 vt100
