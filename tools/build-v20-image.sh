#!/bin/sh
# Assemble the R36S-V20 image using the open Arch-R hardware stack.
set -eu

if [ "$#" -lt 5 ] || [ "$#" -gt 6 ]; then
    echo "Usage: $0 <ArchR-clone.img[.gz]> <panel.dtbo> <joypad.ko> <rootfs.squashfs> <output.img> [size_mib]" >&2
    exit 2
fi

repo=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
donor=$(realpath "$1")
overlay=$(realpath "$2")
joypad=$(realpath "$3")
rootfs=$(realpath "$4")
out=$5
size=${6:-4096}
version=${VERSION:-0.35-v20}

if [ "$out" -ef "$donor" ] || [ "$out" -ef "$overlay" ] ||
   [ "$out" -ef "$joypad" ] || [ "$out" -ef "$rootfs" ]; then
    echo "The output image must differ from the input files." >&2
    exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
board="$repo/board/r36s-v20"
kernel="$work/kernel/Image"
dtb="$work/kernel/rk3326-r36s-v20.dtb"
mkdir "$work/data"
cp "$board/data/emulators.toml" "$work/data/"

python3 "$repo/tools/prepare-v20-kernel.py" --archr-image "$donor" \
    --panel-overlay "$overlay" --joypad-module "$joypad" --out "$work/kernel"
unsquashfs -no-progress -d "$work/root" "$rootfs"
if ! grep -Fq 'archr-singleadc-joypad.ko' "$work/root/etc/init.d/rcS" ||
   [ ! -L "$work/root/sbin/insmod" ]; then
    echo "Rebuild the DeepOS rootfs with the current rcS and BusyBox insmod." >&2
    exit 1
fi
cp -R "$work/kernel/lib" "$work/root/"
rootfs="$work/rootfs.squashfs"
python3 "$repo/tools/build-rootfs.py" --root "$work/root" --out "$rootfs" --check
python3 "$repo/tools/mkboot.py" --kernel "$kernel" --dtb "$dtb" --out "$work/boot" \
    --extlinux "$board/boot/extlinux/archr-v20.conf" --boot-script "$board/boot/archr-v20.cmd" \
    --logo "$repo/branding/deepos-boot.bmp" --extra "$board/boot/README-FIRST.txt" --version "$version"
python3 "$repo/tools/preflight.py" --root "$repo" --skip-image --loader-donor "$donor" \
    --kernel "$kernel" --dtb "$dtb" --boot "$work/boot" --rootfs "$rootfs"
python3 "$repo/tools/mkimage.py" --out "$out" --size-mib "$size" --loader-donor "$donor" \
    --boot "$work/boot" --sys-a "$rootfs" --data "$work/data"
python3 "$repo/tools/verify-image.py" --loader-donor "$donor" "$out"
