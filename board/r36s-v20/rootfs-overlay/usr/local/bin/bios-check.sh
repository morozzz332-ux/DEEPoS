#!/bin/sh
# Which emulated systems still need a BIOS file?
#
# The firmware dumps themselves cannot be shipped with DEEPoS, so the boot report
# says what is present instead of leaving the user with a game that starts and
# shows a black screen. Output is a stable key=value list (the PC-side reader
# diffs it), the same shape as /flash/report/checks.txt.
#
# Usage: bios-check.sh [<bios-dir>]
set -u

table=/usr/share/deepos/bios-required.tsv
report=${1:-}
bios_dirs=${DEEPOS_BIOS_DIRS:-/storage/bios /games/bios}

found_any=0
ready=0
wanted=0
out=$(mktemp /tmp/bios.XXXXXX 2>/dev/null || echo /tmp/bios.txt)

# A system is ready when at least one of its listed files exists (PS1 has three
# region dumps, Dreamcast two, and any single one is enough).
while IFS="	" read -r system path note; do
    case "$system" in ""|\#*) continue ;; esac
    wanted=$((wanted + 1))
    hit=
    for dir in $bios_dirs; do
        [ -n "$dir" ] || continue
        if [ -e "$dir/$path" ]; then
            hit=$dir/$path
            break
        fi
    done
    if [ -n "$hit" ]; then
        ready=$((ready + 1))
        printf '%s=%s\n' "$system" "$hit" >> "$out"
    else
        printf '%s=missing(%s)\n' "$system" "$path" >> "$out"
    fi
done < "$table"

{
    echo "bios_ready=$ready/$wanted"
    for dir in $bios_dirs; do
        [ -d "$dir" ] || continue
        echo "bios_dir=$dir"
        found_any=1
    done
    [ "$found_any" = 1 ] || echo "bios_dir=none"
    sort "$out"
} > "$out.sorted" 2>/dev/null
[ -s "$out.sorted" ] && cat "$out.sorted"
if [ -n "$report" ] && [ -s "$out.sorted" ]; then
    cp "$out.sorted" "$report" 2>/dev/null || true
fi
rm -f "$out" "$out.sorted"
exit 0
