#!/bin/sh
# Copy only the zones presented by the firmware.
set -eu
zones=$1
stage=$2
sed -n 's/^ZONE("\([^"]*\)",.*)/\1/p' "$zones" | while IFS= read -r zone; do
    install -D -m 0644 "/usr/share/zoneinfo/$zone" "$stage/usr/share/zoneinfo/$zone"
done
ln -sfn /run/deepos-localtime "$stage/etc/localtime"
