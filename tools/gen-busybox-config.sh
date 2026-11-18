#!/bin/sh
# Regenerate board/r36s-v20/busybox.config from busybox defconfig plus the
# applets DEEPoS needs at boot. Run inside deepos-cross:local (or any host with
# aarch64-linux-gnu-gcc) after bumping BB_VER.
#
#   sh tools/gen-busybox-config.sh
#
# The result is committed, so a normal build does not need to run this script.
set -eu

REPO=${REPO:-/w}
BB_VER=${BB_VER:-1.36.1}
CACHE=${CACHE:-$REPO/build/cache}
CROSS=${CROSS:-aarch64-linux-gnu-}
TAR="busybox-${BB_VER}.tar.bz2"
WORK=${WORK:-/tmp/bbgen}

mkdir -p "$CACHE"
if [ ! -f "$CACHE/$TAR" ]; then
    wget -qO "$CACHE/$TAR" "https://busybox.net/downloads/$TAR"
fi

rm -rf "$WORK"
mkdir -p "$WORK"
tar -xjf "$CACHE/$TAR" -C "$WORK" --strip-components=1

cd "$WORK"
make -s ARCH=arm64 CROSS_COMPILE="$CROSS" defconfig

# Applets and features required by board/r36s-v20/rootfs-overlay/etc/init.d/rcS
# and by the launcher: mdev, mount/umount, ip/udhcpc, tar/gzip, ash as shell.
for sym in \
    STATIC MDEV INIT ASH MOUNT UMOUNT SWITCH_ROOT IP UDHCPC TAR GZIP \
    FEATURE_MDEV_CONF FEATURE_MDEV_RENAME FEATURE_MDEV_EXEC \
    FEATURE_SH_STANDALONE FEATURE_PREFER_APPLETS \
    CAT CP LS MKDIR RM MV GREP SED AWK FIND XARGS SLEEP DATE DF FREE PS \
    DMESG REBOOT POWEROFF HALT SYNC CHMOD CHOWN LN READLINK BASENAME DIRNAME \
    HEAD TAIL CUT TR WC SORT UNIQ TOP KILL; do
    if grep -q "^CONFIG_${sym}=y" .config; then
        continue
    fi
    if grep -q "^# CONFIG_${sym} is not set" .config; then
        sed -i "s/^# CONFIG_${sym} is not set/CONFIG_${sym}=y/" .config
    else
        printf 'CONFIG_%s=y\n' "$sym" >> .config
    fi
done

make -s ARCH=arm64 CROSS_COMPILE="$CROSS" oldconfig >/dev/null
cp .config "$REPO/board/r36s-v20/busybox.config"

echo "wrote board/r36s-v20/busybox.config"
grep -E '^CONFIG_(STATIC|MDEV|INIT|ASH|MOUNT|IP|UDHCPC|TAR)=' "$REPO/board/r36s-v20/busybox.config"
