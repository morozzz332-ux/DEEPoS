#!/bin/sh
# Layout the optional PortMaster userland in the immutable rootfs.
set -eu
root=$1
package=$2
opt=$root/opt/deepos
mkdir -p "$opt" "$root/lib" "$root/usr/bin" "$root/usr/lib" "$root/opt/tools"
python3 -m tarfile --filter data -e "$package" "$opt"
runtime=$opt/portmaster/runtime
test -x "$runtime/bin/bash"
test -x "$runtime/bin/python3"
test -x "$runtime/lib/ld-linux-aarch64.so.1"
test -r "$opt/portmaster/PortMaster/utils/pm_launch.txt"
ln -sf /opt/deepos/portmaster/runtime/bin/bash "$root/bin/bash"
ln -sf /opt/deepos/portmaster/runtime/bin/python3 "$root/usr/bin/python3"
ln -sf /opt/deepos/portmaster/runtime/lib/ld-linux-aarch64.so.1 "$root/lib/ld-linux-aarch64.so.1"
ln -sf /opt/deepos/portmaster/runtime/lib/ld-linux-aarch64.so.1 "$root/usr/lib/ld-linux-aarch64.so.1"
ln -sf /opt/deepos/portmaster/runtime/lib/libc.so.6 "$root/lib/libc.so.6"
ln -sf /data/portmaster/PortMaster "$root/opt/tools/PortMaster"
ln -sf /storage "$root/roms"
