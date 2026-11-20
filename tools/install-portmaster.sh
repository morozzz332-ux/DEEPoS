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

# glibc 2.34 merged libpthread/libdl/librt/libutil/libresolv into libc, but port
# binaries still carry the old DT_NEEDED names and would otherwise die with
# "error while loading shared libraries: libpthread.so.0".
for stub in libpthread.so.0 libdl.so.2 librt.so.1 libutil.so.1 libresolv.so.2; do
    ln -sf libc.so.6 "$runtime/lib/$stub"
    ln -sf /opt/deepos/portmaster/runtime/lib/libc.so.6 "$root/lib/$stub"
done

# Keep the SDL controller database below MAX_ARG_STRLEN so port children can exec.
# Resolve the helper relative to this script: build-rootfs.sh calls us from the
# busybox build directory, so a bare "tools/..." path does not exist.
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$here/curate-controllerdb.py" "$opt/portmaster"

ln -sf /data/portmaster/PortMaster "$root/opt/tools/PortMaster"
ln -sf /storage "$root/roms"
