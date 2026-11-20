#!/bin/sh
# Which emulated systems still need a BIOS file?
#
# The firmware dumps themselves cannot be shipped with DEEPoS, so the boot report
# says what is present instead of leaving the user with a game that starts and
# shows a black screen. Output is a stable key=value list (the PC-side reader
# diffs it), the same shape as /flash/report/checks.txt.
#
# A system with several listed files is ready when ANY of them exists: PS1 has
# three region dumps, Sega CD three, Dreamcast two. Systems marked "hle" in the
# table still boot without a dump, so they are reported as optional instead of
# missing.
#
# Usage: bios-check.sh [<report-file>]
set -u

table=/usr/share/deepos/bios-required.tsv
report=${1:-}
bios_dirs=${DEEPOS_BIOS_DIRS:-/storage/bios /games/bios}

tmp=$(mktemp /tmp/bios.XXXXXX 2>/dev/null || echo /tmp/bios-check.txt)

awk -F '\t' -v dirs="$bios_dirs" '
    /^#/ || NF < 2 { next }
    {
        sub(/\r$/, "")
        sysname = $1
        if (!(sysname in seen)) {
            order[++count] = sysname
            seen[sysname] = 1
        }
        paths[sysname] = (sysname in paths ? paths[sysname] : "") $2 " "
        if ($4 == "hle") hle[sysname] = 1
    }
    END {
        dircount = split(dirs, d, " ")
        for (k = 1; k <= dircount; k++)
            if (system("test -d \"" d[k] "\"") == 0) {
                print "bios_dir=" d[k]
                dirs_seen++
            }
        if (dirs_seen == 0) print "bios_dir=none"

        ready = 0; missing = 0; optional = 0
        for (i = 1; i <= count; i++) {
            sysname = order[i]
            hit = ""
            n = split(paths[sysname], list, " ")
            for (j = 1; j <= n && hit == ""; j++) {
                if (list[j] == "") continue
                for (k = 1; k <= dircount; k++)
                    if (system("test -e \"" d[k] "/" list[j] "\"") == 0) {
                        hit = d[k] "/" list[j]
                        break
                    }
            }
            if (hit != "") {
                ready++
                print sysname "=" hit > "/dev/stderr"
            } else if (sysname in hle) {
                optional++
                print sysname "=optional(" list[1] ")" > "/dev/stderr"
            } else {
                missing++
                print sysname "=missing(" list[1] ")" > "/dev/stderr"
            }
        }
        printf "bios_ready=%d/%d\n", ready, count
        printf "bios_missing=%d\n", missing
        printf "bios_optional=%d\n", optional
    }
' "$table" 2> "$tmp.lines" > "$tmp.keys"

{
    cat "$tmp.keys"
    sort "$tmp.lines"
} > "$tmp"

cat "$tmp"
if [ -n "$report" ]; then
    cp "$tmp" "$report" 2>/dev/null || true
fi
rm -f "$tmp" "$tmp.keys" "$tmp.lines"

exit 0
