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
WORK=${WORK:-$REPO/build/uboot-work}
CROSS=${CROSS:-aarch64-linux-gnu-}
CROSS32=${CROSS32:-arm-none-eabi-}
UBOOT_REF=${UBOOT_REF:-next-dev}
RKBIN_REF=${RKBIN_REF:-master}
SOC=${SOC:-rk3326}
JOBS=${JOBS:-4}

mkdir -p "$OUT" "$WORK"

clone() {
    url=$1; ref=$2; dir=$3
    if [ ! -d "$dir/.git" ]; then
        echo "cloning $url ($ref)"
        git clone --depth 1 -b "$ref" "$url" "$dir"
    fi
}

clone https://github.com/rockchip-linux/u-boot.git "$UBOOT_REF" "$WORK/u-boot"
clone https://github.com/rockchip-linux/rkbin.git "$RKBIN_REF" "$WORK/rkbin"

export CROSS_COMPILE="$CROSS"
export CROSS_COMPILE_ARM32="$CROSS32"
export RKBIN="$WORK/rkbin"
export PATH="$WORK/rkbin/tools:$PATH"

cd "$WORK/u-boot"

echo "--- rk3326 support in this tree ---"
ls configs/ | grep -i "$SOC" || echo "no $SOC defconfig"
ls arch/arm/dts/ 2>/dev/null | grep -i "$SOC" || echo "no $SOC dts"

DEFCONFIG=""
for cand in "${SOC}_defconfig" "evb-${SOC}_defconfig" "${SOC}-aarch32_defconfig"; do
    if [ -f "configs/$cand" ]; then DEFCONFIG="$cand"; break; fi
done
if [ -z "$DEFCONFIG" ]; then
    echo "no usable defconfig for $SOC" >&2
    exit 1
fi
echo "--- configuring with $DEFCONFIG ---"
make distclean >/dev/null 2>&1 || true
make "$DEFCONFIG"

echo "--- building (native arch from defconfig) ---"
# The vendor tree predates modern GCC and trips -Werror in unrelated files
# (common/edid.c); warnings there are not our bugs, so keep them non-fatal.
make -j"$JOBS" KCFLAGS="-Wno-error" 2>&1 | tail -20 || true
echo "--- produced artifacts ---"
ls -l idbloader.img u-boot.itb u-boot.bin spl/u-boot-spl.bin tpl/u-boot-tpl.bin 2>/dev/null || true

if [ ! -f idbloader.img ]; then
    if [ -f tpl/u-boot-tpl.bin ] && [ -f spl/u-boot-spl.bin ]; then
        echo "--- assembling idbloader from tpl + spl ---"
        ./tools/mkimage -n "$SOC" -T rksd -d tpl/u-boot-tpl.bin idbloader.img
        cat spl/u-boot-spl.bin >> idbloader.img
    elif [ -f spl/u-boot-spl.bin ]; then
        echo "--- assembling idbloader from spl only ---"
        ./tools/mkimage -n "$SOC" -T rksd -d spl/u-boot-spl.bin idbloader.img
    else
        echo "no tpl/spl artifacts produced; cannot build idbloader" >&2
        exit 1
    fi
fi

if [ ! -f u-boot.itb ]; then
    echo "--- building u-boot.itb from u-boot.bin + BL31 ---"
    BL31=$(ls "$RKBIN/${SOC^^}/${SOC^^}-BL31-"*.bin 2>/dev/null | tail -1 || true)
    if [ -z "$BL31" ]; then
        # older rkbin trees keep the ARM Trusted Firmware blobs under bin/rk33/
        BL31=$(ls "$RKBIN"/bin/rk33/"${SOC}"_bl31_*.elf 2>/dev/null | tail -1 || true)
    fi
    if [ -z "$BL31" ]; then
        echo "no BL31 blob for $SOC in rkbin; cannot build u-boot.itb" >&2
        exit 1
    fi
    echo "BL31=$BL31"
    case "$BL31" in
        *.elf) cp "$BL31" bl31.elf; BL31_ARG=bl31.elf ;;
        *)     cp "$BL31" bl31.bin; BL31_ARG=bl31.bin ;;
    esac
    make -j"$JOBS" KCFLAGS="-Wno-error" BL31="$PWD/$BL31_ARG" u-boot.itb 2>&1 | tail -15
fi

cp idbloader.img "$OUT/idbloader.img"
cp u-boot.itb "$OUT/u-boot.itb"
{
    echo "uboot_ref: $UBOOT_REF"
    echo "rkbin_ref: $RKBIN_REF"
    echo "defconfig: $DEFCONFIG"
    echo "soc: $SOC"
    echo "idbloader_bytes: $(stat -c %s "$OUT/idbloader.img")"
    echo "uboot_itb_bytes: $(stat -c %s "$OUT/u-boot.itb")"
    echo "idbloader_sha256: $(sha256sum "$OUT/idbloader.img" | cut -d' ' -f1)"
    echo "uboot_itb_sha256: $(sha256sum "$OUT/u-boot.itb" | cut -d' ' -f1)"
    echo "built_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/BUILD.txt"
cat "$OUT/BUILD.txt"
echo "uboot build OK"
