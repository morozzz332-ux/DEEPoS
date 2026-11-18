#!/bin/sh
# Renders every launcher screen into PPM files (prototype smoke check).
# Usage (inside container): sh tests/ci/render-all.sh /w /w/out
set -e
W="${1:-/w}"
OUT="${2:-/w/out}"
BIN="$W/apps/launcher/launcher"

rm -rf /tmp/roms /tmp/data "$OUT"
mkdir -p /tmp/roms /tmp/data "$OUT"

mk() { # mk <system> <ext> <count>
    sys="$1"; ext="$2"; n="$3"
    mkdir -p "/tmp/roms/$sys"
    i=1
    while [ "$i" -le "$n" ]; do
        printf 'x' > "/tmp/roms/$sys/game$i.$ext"
        i=$((i + 1))
    done
}

mk md bin 312
mk snes sfc 286
mk psx chd 110
mk gba gba 204
mk psp iso 48
mk dc gdi 36
mk n64 z64 52
mk gb gb 167
mk gbc gbc 153
mk nes nes 198
mk arcade zip 241
mk sms sms 94
mk ports sh 0

cat > /tmp/data/continue.tsv <<'TSV'
Sonic 3 & Knuckles	MEGA DRIVE	12 мин	2	1
Crash Bandicoot 2	PLAYSTATION	1 ч 04	-1	0
Lumines	PSP	46 мин	0	1
Streets of Rage 2	MEGA DRIVE	вчера	-1	0
Mario Kart 64	NINTENDO 64	вчера	-1	0
TSV

for s in continue systems games settings modules files info; do
    "$BIN" --roms /tmp/roms --data /tmp/data --screen "$s" \
        --out "$OUT/$s.ppm" --battery 78 --clock 14:32
done

echo "rendered:"
ls -1 "$OUT"
