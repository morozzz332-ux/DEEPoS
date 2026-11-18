#!/bin/sh
# Build the Rockchip boot chain (idbloader.img + u-boot.itb) for RK3326.
#
# Mainline U-Boot has no RK3326 support (no defconfig, no DTS, no board), so the
# only reproducible source today is the vendor fork rockchip-linux/u-boot with a
# BL31 blob from rockchip-linux/rkbin. This is a documented, pinned exception:
# everything above U-Boot (kernel, DTB, rootfs, userland) is ours.
#
# Outputs: build/uboot/{idbloader.img,u-boot.itb,BUILD.txt}
set -e

REPO=${REPO:-/w}
OUT=${OUT:-$REPO/build/uboot}
WORK=${WORK:-/tmp/uboot-work}
CROSS=${CROSS:-aarch64-linux-gnu-}
UBOOT_REF=${UBOOT_REF:-next-dev}
RKBIN_REF=${RKBIN_REF:-master}
SOC=${SOC:-rk3326}

mkdir -p "$OUT" "$WORK"

clone() {
    url=$1; ref=$2; dir=$3
    if [ ! -d "$dir/.git" ]; then
        git clone --depth 1 -b "$ref" "$url" "$dir"
    fi
}

clone https://github.com/rockchip-linux/u-boot.git "$UBOOT_REF" "$WORK/u-boot"
clone https://github.com/rockchip-linux/rkbin.git "$RKBIN_REF" "$WORK/rkbin"

export CROSS_COMPILE="$CROSS"
export RKBIN="$WORK/rkbin"
export PATH="$WORK/rkbin/tools:$PATH"

cd "$WORK/u-boot"
make distclean >/dev/null 2>&1 || true
make "$SOC" CROSS_COMPILE="$CROSS" >/dev/null 2>&1 || true

# The vendor build.sh pairs SPL + BL31 into a bootable itb; fall back to plain
# make targets when build.sh is unavailable.
if [ -x ./build.sh ]; then
    echo "building with vendor build.sh ($SOC)"
    ./build.sh "$SOC" 2>&1 | tail -20
fi

if [ ! -f idbloader.img ]; then
    echo "idbloader.img missing; building SPL by hand"
    make "$(echo "$SOC" | sed 's/rk/rk/')_defconfig" >/dev/null 2>&1 || true
    make CROSS_COMPILE="$CROSS" ARCH=arm -j"$(nproc)" u-boot-spl.bin >/dev/null
    ./tools/mkimage -n "$SOC" -T rksd -d spl/u-boot-spl.bin idbloader.img
fi

if [ ! -f u-boot.itb ]; then
    echo "u-boot.itb missing; building itb from u-boot.bin + BL31"
    BL31=$(ls "$RKBIN/${SOC^^}"/"${SOC^^}"-BL31-*.bin 2>/dev/null | tail -1)
    if [ -z "$BL31" ]; then
        echo "no BL31 blob for $SOC in rkbin; cannot build u-boot.itb" >&2
        exit 1
    fi
    cp "$BL31" bl31.bin
    make CROSS_COMPILE="$CROSS" ARCH=arm -j"$(nproc)" BL31=bl31.bin u-boot.itb
fi

cp idbloader.img "$OUT/idbloader.img"
cp u-boot.itb "$OUT/u-boot.itb"
{
    echo "uboot_ref: $UBOOT_REF"
    echo "rkbin_ref: $RKBIN_REF"
    echo "soc: $SOC"
    echo "idbloader_bytes: $(stat -c %s "$OUT/idbloader.img")"
    echo "uboot_itb_bytes: $(stat -c %s "$OUT/u-boot.itb")"
    echo "idbloader_sha256: $(sha256sum "$OUT/idbloader.img" | cut -d' ' -f1)"
    echo "uboot_itb_sha256: $(sha256sum "$OUT/u-boot.itb" | cut -d' ' -f1)"
    echo "built_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/BUILD.txt"
cat "$OUT/BUILD.txt"
echo "uboot build OK"
