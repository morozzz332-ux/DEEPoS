#!/bin/sh
# Build the DEEPoS kernel image and board DTB from source.
#
# Runs inside deepos-cross:local (Ubuntu + gcc-aarch64-linux-gnu). The kernel
# tarball is cached on the host in build/cache; sources are extracted to /tmp
# because the container filesystem is discarded after the run.
#
# Outputs (host, via the /w mount):
#   build/kernel/Image                       uncompressed arm64 kernel
#   build/kernel/rk3326-r36s-v20.dtb         board device tree
#   build/kernel/BUILD.txt                   kernel version, config sha, sizes
set -e

KVER=${KVER:-6.12.56}
TARBALL="linux-${KVER}.tar.xz"
URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/${TARBALL}"
CACHE=${CACHE:-/w/build/cache}
REPO=${REPO:-/w}
WORK=${WORK:-$REPO/build/kbuild}
OUT="$REPO/build/kernel"
CROSS=aarch64-linux-gnu-

mkdir -p "$CACHE" "$OUT"

if [ ! -f "$CACHE/$TARBALL" ]; then
    echo "downloading $TARBALL"
    wget -qO "$CACHE/$TARBALL" "$URL"
fi

if [ ! -d "$WORK" ]; then
    echo "extracting $TARBALL"
    mkdir -p "$WORK"
    tar -xJf "$CACHE/$TARBALL" -C "$WORK" --strip-components=1 && touch "$WORK/.extracted"
fi

cd "$WORK"

echo "configuring"
make -s ARCH=arm64 CROSS_COMPILE=$CROSS defconfig
ARCH=arm64 scripts/kconfig/merge_config.sh .config "$REPO/board/r36s-v20/linux.config" >/dev/null
make -s ARCH=arm64 CROSS_COMPILE=$CROSS olddefconfig

echo "building Image (-j$(nproc))"
make -s -j"$(nproc)" ARCH=arm64 CROSS_COMPILE=$CROSS Image

echo "compiling board DTB"
gcc -E -P -w -Dlinux=linux -x assembler-with-cpp \
    -I arch/arm64/boot/dts \
    -I arch/arm64/boot/dts/rockchip \
    -I include \
    "$REPO/board/r36s-v20/dts/rk3326-r36s-v20.dts" -o /tmp/board.dts
dtc -I dts -O dtb -o /tmp/board.dtb /tmp/board.dts 2>/tmp/dtc.log || {
    echo "dtc failed:"; cat /tmp/dtc.log; exit 1;
}

cp arch/arm64/boot/Image "$OUT/Image"
cp /tmp/board.dtb "$OUT/rk3326-r36s-v20.dtb"
cp .config "$OUT/kernel.config"

{
    echo "kernel: ${KVER}"
    echo "config_sha256: $(sha256sum "$OUT/kernel.config" | cut -d' ' -f1)"
    echo "image_bytes: $(stat -c %s "$OUT/Image")"
    echo "dtb_bytes: $(stat -c %s "$OUT/rk3326-r36s-v20.dtb")"
    echo "built_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/BUILD.txt"

cat "$OUT/BUILD.txt"
echo "kernel build OK"
