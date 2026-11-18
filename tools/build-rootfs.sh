#!/bin/sh
# Assemble the DEEPoS root filesystem and pack it as squashfs.
#
# Runs inside deepos-cross:local (aarch64 cross toolchain + squashfs-tools).
# Pieces:
#   1. busybox (static-ish, our board/busybox.config) as /bin/busybox + applets
#   2. our own binaries cross-compiled: launcher, modd, saved
#   3. rootfs overlay: /etc (os-release, fstab, inittab, rcS), /data, /storage
#   4. module tree for thermal/saves (bash modules, shipped read-only)
#
# Outputs: build/rootfs.squashfs and build/rootfs-stage/ (third_party/, git-ignored)
set -e

REPO=${REPO:-/w}
OUT=${OUT:-$REPO/build/rootfs.squashfs}
STAGE=${STAGE:-$REPO/build/rootfs-stage}
CACHE=${CACHE:-$REPO/build/cache}
WORK=${WORK:-/tmp/rootfs-work}
BB_VER=${BB_VER:-1.36.1}
BB_TAR="busybox-${BB_VER}.tar.bz2"
BB_URL="https://busybox.net/downloads/${BB_TAR}"
CROSS=${CROSS:-aarch64-linux-gnu-}

mkdir -p "$CACHE" "$STAGE" "$WORK"

# --- 1. busybox ------------------------------------------------------------
if [ ! -f "$CACHE/$BB_TAR" ]; then
    echo "downloading busybox ${BB_VER}"
    wget -qO "$CACHE/$BB_TAR" "$BB_URL"
fi

if [ ! -f "$WORK/busybox/.config" ]; then
    echo "extracting busybox"
    mkdir -p "$WORK/busybox"
    tar -xjf "$CACHE/$BB_TAR" -C "$WORK/busybox" --strip-components=1
    cp "$REPO/board/r36s-v20/busybox.config" "$WORK/busybox/.config"
fi

cd "$WORK/busybox"
make -s ARCH=arm64 CROSS_COMPILE="$CROSS" oldconfig >/dev/null
make -s -j"$(nproc)" ARCH=arm64 CROSS_COMPILE="$CROSS" >/dev/null
rm -rf "$STAGE"
mkdir -p "$STAGE"
make -s ARCH=arm64 CROSS_COMPILE="$CROSS" CONFIG_PREFIX="$STAGE" install >/dev/null

# --- 2. our binaries ------------------------------------------------------
echo "building DEEPoS userland for aarch64"
for app in launcher modd saved; do
    make -s -C "$REPO/apps/$app" clean >/dev/null 2>&1 || true
    make -s -C "$REPO/apps/$app" CC="${CROSS}gcc" >/dev/null
done
mkdir -p "$STAGE/usr/bin"
for app in launcher modd saved; do
    cp "$REPO/apps/$app/$app" "$STAGE/usr/bin/$app"
    make -s -C "$REPO/apps/$app" clean >/dev/null 2>&1 || true
done

# --- 3. overlay -----------------------------------------------------------
cp -a "$REPO/board/r36s-v20/rootfs-overlay/." "$STAGE/"
mkdir -p "$STAGE/proc" "$STAGE/sys" "$STAGE/dev" "$STAGE/run" "$STAGE/tmp" \
         "$STAGE/data" "$STAGE/storage" "$STAGE/usr/share/deepos"
chmod 1777 "$STAGE/tmp"
[ -e "$STAGE/init" ] || ln -sf /bin/busybox "$STAGE/init"
[ -e "$STAGE/sbin/init" ] || ln -s ../bin/busybox "$STAGE/sbin/init"
[ -e "$STAGE/linuxrc" ] || ln -sf /bin/busybox "$STAGE/linuxrc"

# --- 4. modules -----------------------------------------------------------
mkdir -p "$STAGE/usr/share/deepos/modules"
cp -a "$REPO/modules/thermal" "$REPO/modules/saves" "$STAGE/usr/share/deepos/modules/"

# --- pack -----------------------------------------------------------------
echo "packing squashfs"
python3 "$REPO/tools/build-rootfs.py" --root "$STAGE" --out "$OUT" --check
ls -l "$OUT"
echo "rootfs build OK"
