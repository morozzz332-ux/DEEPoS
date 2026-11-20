#!/bin/sh
# DEEPoS saves helper - archives RetroArch saves/states into /storage/backup/saves.
#
# usage: saves-backup.sh <module-data-dir>
# Environment overrides exist for host tests: SAVES_DIR, STATES_DIR, BACKUP_DIR,
# KEEP (number of archives to retain).
set -eu

DATA="${1:?usage: saves-backup.sh <module-data-dir>}"
SAVES="${SAVES_DIR:-/storage/.config/retroarch/saves}"
STATES="${STATES_DIR:-/storage/.config/retroarch/states}"
BACKUP="${BACKUP_DIR:-/storage/backup/saves}"
KEEP="${KEEP:-10}"

[ -r "$DATA/request" ] || exit 1
[ "$(cat "$DATA/request")" = backup ] || exit 1
rm -f "$DATA/request"
mkdir -p "$BACKUP" "$DATA"

stamp=$(date -u +%Y%m%d-%H%M%S)
archive="$BACKUP/saves-$stamp.tar.gz"
files=0
tmp_list="$DATA/.files"
: > "$tmp_list"

for dir in "$SAVES" "$STATES"; do
    [ -d "$dir" ] || continue
    find "$dir" -type f >> "$tmp_list" 2>/dev/null || true
done

files=$(wc -l < "$tmp_list" | tr -d ' ')
rm -f "$tmp_list"

set --
[ ! -d "$SAVES" ] || set -- "$@" -C "$(dirname "$SAVES")" "$(basename "$SAVES")"
[ ! -d "$STATES" ] || set -- "$@" -C "$(dirname "$STATES")" "$(basename "$STATES")"
if [ "$files" -gt 0 ] && tar -czf "$archive.tmp" "$@" 2>/dev/null; then
    mv "$archive.tmp" "$archive"
    ok=true
else
    rm -f "$archive.tmp"
    archive=""
    ok=false
fi

# rotate: newest KEEP archives only
if [ -n "$archive" ]; then
    ls -1t "$BACKUP"/saves-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while IFS= read -r old; do
        rm -f "$old"
    done
fi

bytes=0
[ -n "$archive" ] && bytes=$(wc -c < "$archive" | tr -d ' ')
ts=$(date +%s)

printf '{"ok":%s,"ts":%s,"file":"%s","bytes":%s,"files":%s}\n' \
    "$ok" "$ts" "$archive" "$bytes" "$files" > "$DATA/status.tmp"
mv "$DATA/status.tmp" "$DATA/status"
chmod 644 "$DATA/status" 2>/dev/null || true
[ "$ok" = true ]
