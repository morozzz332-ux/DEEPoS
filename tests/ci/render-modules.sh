#!/bin/sh
# Render the МОДУЛИ screen with a live modd supervisor (CI / local demo).
set -eu
WORK=${1:-/tmp/lmod}
ROOT=${2:-/w}
rm -rf "$WORK"
mkdir -p "$WORK/data" "$WORK/roms/md"
cp -r "$ROOT/tests/fixtures/modd/." "$WORK/modules/"
i=0
while [ $i -lt 3 ]; do : > "$WORK/roms/md/g$i.md"; i=$((i + 1)); done

"$ROOT/apps/modd/modd" --modules "$WORK/modules" --socket "$WORK/modd.sock" --data "$WORK/data" \
    >"$WORK/modd.log" 2>&1 &
pid=$!
sleep 1

"$ROOT/apps/launcher/launcher" --roms "$WORK/roms" --data "$WORK/data" \
    --modules-socket "$WORK/modd.sock" --screen modules --out "$WORK/modules.ppm"

kill $pid 2>/dev/null || true
wait $pid 2>/dev/null || true
echo "rendered $WORK/modules.ppm"
