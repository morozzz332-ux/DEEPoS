#!/bin/sh
# Launch a core from the optional, locally imported Arch-R runtime.
set -eu

runtime=${DEEPOS_EMULATORS:-/data/emus}
config=${DEEPOS_RETROARCH_CONFIG:-/storage/.config/retroarch}
[ "$#" -eq 2 ] || exit 2
core=$runtime/cores/$1_libretro.so
rom=$2
[ -x "$runtime/retroarch" ] && [ -r "$core" ] || {
    echo "RetroArch or the core is missing: $core" >&2
    exit 126
}

mkdir -p "$config/saves" "$config/states"
cfg=$config/retroarch.cfg
if [ ! -e "$cfg" ]; then
    cp /usr/share/deepos/retroarch.cfg "$cfg"
fi
hotkeys=/usr/share/deepos/retroarch-hotkeys.cfg
overrides=/run/deepos-retroarch.cfg
tmp=$(mktemp /run/deepos-retroarch.XXXXXX)
print_overrides() {
    cat "$hotkeys" && /usr/bin/launcher --print-retroarch-config || return 1
    case "$rom" in /games/*)
        for bios in /games/bios /games/roms/bios; do
            [ -d "$bios" ] || continue
            for entry in "$bios"/*; do
                [ -f "$entry" ] || [ -d "$entry" ] || continue
                printf 'system_directory = "%s"\n' "$bios"
                return
            done
        done ;;
    esac
}
if print_overrides > "$tmp" &&
   mv -f "$tmp" "$overrides"; then
    hotkeys=$overrides
else
    rm -f "$tmp"
fi
[ -r "$rom" ] || exit 2

# Keep the donor loader and libraries together. A native build can omit lib/.
if [ -x "$runtime/lib/ld-linux-aarch64.so.1" ]; then
    if [ -f "$runtime/lib/dri/panfrost_dri.so" ] && [ ! -e "$runtime/lib/dri/rockchip_dri.so" ]; then
        # Earlier imports lacked the KMS render-only name used by the VOP.
        ln -s panfrost_dri.so "$runtime/lib/dri/rockchip_dri.so"
    fi
    export LD_LIBRARY_PATH="$runtime/lib"
    export LIBGL_DRIVERS_PATH="$runtime/lib/dri"
    export __EGL_VENDOR_LIBRARY_FILENAMES="$runtime/egl/50_mesa.json"
    export ALSOFT_DRIVERS=alsa
    export ALSA_CONFIG_DIR="$runtime/alsa"
    exec "$runtime/lib/ld-linux-aarch64.so.1" "$runtime/retroarch" \
        --config "$cfg" --appendconfig "$hotkeys" -L "$core" "$rom"
fi
exec "$runtime/retroarch" --config "$cfg" --appendconfig "$hotkeys" -L "$core" "$rom"
