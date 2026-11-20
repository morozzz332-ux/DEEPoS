#!/bin/sh
# Cross-compile the DEEPoS aarch64 userland (launcher, modd, saved, updatr).
#
# Usage: build-userland.sh [--out DIR]
#   --out DIR  copy the binaries into DIR (created if missing) and strip them
#
# Runs inside deepos-cross:local or any host with aarch64-linux-gnu-gcc.
set -eu

OUT=
if [ "${1:-}" = "--out" ]; then
    OUT=$2
fi

APPS=${APPS:-launcher modd saved updatr playdemo}
CROSS=${CROSS:-aarch64-linux-gnu-}
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}

# Ubuntu enables _FORTIFY_SOURCE inside its glibc headers; with -Werror that
# turns bounded snprintf calls into -Wformat-truncation errors. Our buffers are
# bounded by explicit precision widths, so fortify buys us nothing here.
default_flags='-std=c11 -Wall -Wextra -Werror -pedantic'
default_flags="$default_flags -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L -D_GNU_SOURCE -U_FORTIFY_SOURCE -Wno-format-truncation -static"

for app in $APPS; do
    echo "building $app"
    make -s -C "$REPO/apps/$app" clean >/dev/null 2>&1 || true
    optimization=-O2
    [ "$app" != launcher ] || optimization=-Os
    make -s -C "$REPO/apps/$app" CC="${CROSS}gcc" CFLAGS="${CFLAGS:-$optimization $default_flags}"
    if [ -n "$OUT" ]; then
        mkdir -p "$OUT"
        cp "$REPO/apps/$app/$app" "$OUT/$app"
        "${CROSS}strip" -s "$OUT/$app" 2>/dev/null || true
    fi
done

if [ -n "$OUT" ]; then
    ls -l "$OUT"
fi
echo "userland build OK"
