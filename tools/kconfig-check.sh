#!/bin/sh
# Validate board/r36s-v20/linux.config against a real kernel tree.
#
# Runs inside deepos-build:local. The kernel tarball is cached on the host
# (./build/cache) so repeated runs are fast; extraction happens in /tmp.
#
# Steps: rockchip_defconfig -> merge our fragment -> olddefconfig -> verify that
# every "=y" line of the fragment survived, and report symbols the fragment
# asked for that the kernel does not know at all.
set -e

KVER=${KVER:-6.12.56}
TARBALL="linux-${KVER}.tar.xz"
URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/${TARBALL}"
CACHE=${CACHE:-/w/build/cache}
WORK=/tmp/kbuild
REPO=/w

mkdir -p "$CACHE"

if [ ! -f "$CACHE/$TARBALL" ]; then
    echo "downloading $TARBALL"
    if command -v wget >/dev/null 2>&1; then
        wget -qO "$CACHE/$TARBALL" "$URL"
    else
        curl -sSLo "$CACHE/$TARBALL" "$URL"
    fi
fi

rm -rf "$WORK"
mkdir -p "$WORK"
echo "extracting $TARBALL"
tar -xJf "$CACHE/$TARBALL" -C "$WORK" --strip-components=1

cd "$WORK"
make -s ARCH=arm64 defconfig
echo "merging board fragment"
ARCH=arm64 scripts/kconfig/merge_config.sh .config "$REPO/board/r36s-v20/linux.config" >/dev/null
make -s ARCH=arm64 olddefconfig

python3 - "$REPO/board/r36s-v20/linux.config" "$WORK/.config" <<'PY'
import re
import sys

fragment, config = sys.argv[1], sys.argv[2]

want = {}
for line in open(fragment, encoding="utf-8"):
    m = re.match(r"^(CONFIG_[A-Z0-9_]+)=(y|n|m)$", line.strip())
    if m:
        want[m.group(1)] = m.group(2)

have = {}
for line in open(config, encoding="utf-8"):
    m = re.match(r"^(CONFIG_[A-Z0-9_]+)=(.*)$", line.strip())
    if m:
        have[m.group(1)] = m.group(2)
    m = re.match(r"^# (CONFIG_[A-Z0-9_]+) is not set$", line.strip())
    if m:
        have[m.group(1)] = "n"

missing_symbols, unsatisfied, ok = [], [], 0
for sym, val in sorted(want.items()):
    got = have.get(sym)
    if got is None:
        missing_symbols.append(sym)
    elif val == "y" and got != "y":
        unsatisfied.append(f"{sym}: want y, got {got}")
    elif val == "n":
        ok += 1  # disabling a symbol the kernel does not have is harmless
    else:
        ok += 1

print(f"fragment symbols: {len(want)}, satisfied: {ok}")
if missing_symbols:
    print("unknown symbols (kernel does not define them):")
    for s in missing_symbols:
        print("  " + s)
if unsatisfied:
    print("required =y symbols that ended up disabled:")
    for s in unsatisfied:
        print("  " + s)

# Unknown symbols are reported but not fatal (renamed/removed across versions);
# a required driver silently turning off is fatal.
sys.exit(1 if unsatisfied else 0)
PY

echo "kconfig check OK (${KVER})"
