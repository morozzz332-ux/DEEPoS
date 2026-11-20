#!/bin/sh
# Copy module folders explicitly selected from the TF1 USB staging area.
set -u
source=/storage/modules
target=/data/modules
mountpoint -q /storage && mountpoint -q /data || exit 1
[ -d "$source" ] || exit 2
mkdir -p "$target" || exit 1
installed=0
failed=0
for folder in "$source"/*; do
    id=${folder##*/}
    case "$id" in ''|*[!a-zA-Z0-9_-]*) continue ;; esac
    [ "${#id}" -le 47 ] && [ -d "$folder" ] &&
        [ -s "$folder/module.toml" ] && [ -f "$folder/main.sh" ] || continue
    [ ! -e "$target/$id" ] && [ ! -L "$target/$id" ] || continue
    staged=$(mktemp -d "$target/.import.XXXXXX") || exit 1
    if cp -r "$folder/." "$staged/" && chmod 0755 "$staged/main.sh" &&
        touch "$staged/.deepos-roms-import" && mv -T "$staged" "$target/$id"; then
        installed=1
    else
        rm -rf "$staged"
        failed=1
    fi
done
[ "$failed" = 0 ] || exit 1
[ "$installed" = 1 ] || exit 2
