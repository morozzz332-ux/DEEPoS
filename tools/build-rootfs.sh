#!/bin/sh
# Assemble the DEEPoS root filesystem and pack it as squashfs.
#
# Runs inside deepos-cross:local (aarch64 cross toolchain + squashfs-tools).
# Pieces:
#   1. busybox (static, board/busybox.config) as /bin/busybox + applet links
#   2. our own binaries cross-compiled: launcher, modd, saved (static)
#   3. rootfs overlay: /etc (os-release, fstab, inittab, rcS), /data, /storage
#   4. module tree for thermal/saves, shipped read-only under /usr/share/deepos
#
# Outputs: build/rootfs.squashfs and build/rootfs-stage/ (both git-ignored)
set -eu

REPO=${REPO:-/w}
OUT=${OUT:-$REPO/build/rootfs.squashfs}
STAGE=${STAGE:-$REPO/build/rootfs-stage}
CACHE=${CACHE:-$REPO/build/cache}
WORK=${WORK:-/tmp/rootfs-work}
BB_VER=${BB_VER:-1.36.1}
BB_TAR="busybox-${BB_VER}.tar.bz2"
BB_URL="https://busybox.net/downloads/${BB_TAR}"
CROSS=${CROSS:-aarch64-linux-gnu-}
JOBS=${JOBS:-4}

mkdir -p "$CACHE" "$WORK"

# --- 1. busybox ------------------------------------------------------------
if [ ! -f "$CACHE/$BB_TAR" ]; then
    echo "downloading busybox ${BB_VER}"
    wget -qO "$CACHE/$BB_TAR" "$BB_URL"
fi

if [ ! -f "$WORK/busybox/.config" ]; then
    echo "extracting busybox"
    rm -rf "$WORK/busybox"
    mkdir -p "$WORK/busybox"
    tar -xjf "$CACHE/$BB_TAR" -C "$WORK/busybox" --strip-components=1
    cp "$REPO/board/r36s-v20/busybox.config" "$WORK/busybox/.config"
fi

echo "building busybox"
cd "$WORK/busybox"
make -s ARCH=arm64 CROSS_COMPILE="$CROSS" oldconfig >/dev/null
make -j"$JOBS" ARCH=arm64 CROSS_COMPILE="$CROSS" >/dev/null 2>"$WORK/bb-warnings.log" || {
    echo "busybox build failed, tail of log:" >&2
    tail -30 "$WORK/bb-warnings.log" >&2
    exit 1
}

echo "installing busybox"
rm -rf "$STAGE"
mkdir -p "$STAGE"
make -s ARCH=arm64 CROSS_COMPILE="$CROSS" CONFIG_PREFIX="$STAGE" install >/dev/null

# --- 2. our binaries ------------------------------------------------------
echo "building DEEPoS userland for aarch64"
sh "$REPO/tools/build-userland.sh" --out "$STAGE/usr/bin"

# --- 3. overlay -----------------------------------------------------------
echo "applying rootfs overlay"
cp -a "$REPO/board/r36s-v20/rootfs-overlay/." "$STAGE/"
mkdir -p "$STAGE/proc" "$STAGE/sys" "$STAGE/dev" "$STAGE/run" "$STAGE/tmp" \
         "$STAGE/flash" "$STAGE/data" "$STAGE/storage" "$STAGE/usr/share/deepos" "$STAGE/sbin"
chmod 1777 "$STAGE/tmp"
chmod 0755 "$STAGE/etc/init.d/rcS" "$STAGE/usr/local/bin/"*.sh \
           "$STAGE/usr/share/deepos/roms/ports/demo.sh"
[ -e "$STAGE/init" ] || ln -sf /bin/busybox "$STAGE/init"
[ -e "$STAGE/sbin/init" ] || ln -sf ../bin/busybox "$STAGE/sbin/init"
[ -e "$STAGE/linuxrc" ] || ln -sf /bin/busybox "$STAGE/linuxrc"

# --- 4. modules -----------------------------------------------------------
echo "shipping modules"
mkdir -p "$STAGE/usr/share/deepos/modules"
cp -a "$REPO/modules/thermal" "$REPO/modules/saves" "$STAGE/usr/share/deepos/modules/"
chmod 0755 "$STAGE/usr/share/deepos/modules/"*/main.sh \
           "$STAGE/usr/share/deepos/modules/"*/root/*.sh
cp "$REPO/board/r36s-v20/data/emulators.toml" "$STAGE/usr/share/deepos/"
install -D -m 0644 "$REPO/tools/fonts/terminus/OFL.TXT" \
    "$STAGE/usr/share/licenses/deepos/terminus-OFL.txt"

# --- pack -----------------------------------------------------------------
echo "packing squashfs"
python3 "$REPO/tools/build-rootfs.py" --root "$STAGE" --out "$OUT" --check
ls -l "$OUT"
echo "rootfs build OK"
