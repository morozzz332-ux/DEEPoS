#!/bin/sh
# Compile only the board DTB against a kernel source tree.
#
# Reuses build/kernel-src when present (extracted once from the tarball in
# build/cache), so iterating on the DTS takes seconds instead of a full kernel
# rebuild.  Output goes to build/kernel/rk3326-r36s-v20.dtb.
set -eu

VERSION="${KERNEL_VERSION:-6.12.56}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${KERNEL_SRC:-$ROOT/build/kernel-src}"
CACHE="$ROOT/build/cache/linux-$VERSION.tar.xz"
OUT="$ROOT/build/kernel"
DTS="$ROOT/board/r36s-v20/dts/rk3326-r36s-v20.dts"

if [ ! -d "$SRC/include/dt-bindings" ]; then
    [ -f "$CACHE" ] || { echo "dtb: missing $CACHE (run tools/build-kernel.sh once)" >&2; exit 1; }
    echo "dtb: extracting kernel source to $SRC"
    mkdir -p "$SRC"
    tar -xJf "$CACHE" -C "$SRC" --strip-components=1
fi

mkdir -p "$OUT"
PRE="$OUT/.pre.dts"
gcc -E -P -w -Dlinux=linux -x assembler-with-cpp \
    -I "$SRC/include" \
    -I "$SRC/arch/arm64/boot/dts" \
    -I "$SRC/arch/arm64/boot/dts/rockchip" \
    -I "$ROOT/board/r36s-v20/dts" \
    -I "$ROOT/tests/fixtures/dts" \
    "$DTS" -o "$PRE"
dtc -I dts -O dtb -o "$OUT/rk3326-r36s-v20.dtb" "$PRE" 2>"$OUT/.dtc.log" || {
    echo "dtb: dtc failed:" >&2
    sed -n '1,20p' "$OUT/.dtc.log" >&2
    exit 1
}
rm -f "$PRE"
bytes=$(wc -c < "$OUT/rk3326-r36s-v20.dtb")
echo "dtb: OK $bytes bytes"
