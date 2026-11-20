#!/bin/sh
# Launch a core from the optional, locally imported Arch-R runtime.
set -eu

runtime=${DEEPOS_EMULATORS:-/data/emus}
extras=/usr/share/deepos/extra-emulators
config=${DEEPOS_RETROARCH_CONFIG:-/storage/.config/retroarch}
[ "$#" -eq 2 ] || exit 2
# The donor's legacy Flycast 2021 has an unresolved rendering symbol.
if [ "$1" = flycast2021 ] && { [ -r "$runtime/cores/flycast_libretro.so" ] ||
                             [ -r "$extras/cores/flycast_libretro.so" ]; }; then
    set -- flycast "$2"
fi
core=$runtime/cores/$1_libretro.so
rom=$2
if [ "$1" = emuscv ] && [ -r "$extras/cores/emuscv_libretro.so" ]; then
    core=$extras/cores/emuscv_libretro.so
fi
[ -r "$core" ] || core=$extras/cores/$1_libretro.so
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
    *)
        # ROMs on the internal card keep their BIOS next to them on the ROMS
        # partition; without this override a config from another card wins.
        [ -d /storage/bios ] &&
            printf 'system_directory = "%s"\n' /storage/bios ;;
    esac
}
if print_overrides > "$tmp" &&
   mv -f "$tmp" "$overrides"; then
    hotkeys=$overrides
else
    rm -f "$tmp"
fi
[ -r "$rom" ] || exit 2

# dArkOSRE raises the GPU clock for the whole emulator run and restores it on
# exit; panfrost's on-demand governor otherwise idles between frames.
boost=/usr/local/bin/perf-boost.sh
[ -x "$boost" ] && "$boost" on
# Same guard as run-port.sh: a killed wrapper must not leave the GPU pinned.
[ -x "$boost" ] && ( while kill -0 $$ 2>/dev/null; do sleep 5; done; "$boost" off ) >/dev/null 2>&1 &
trap '[ -x "$boost" ] && "$boost" off' EXIT INT TERM
# A single-core SoC with a 60 Hz panel: let the emulator win against the
# launcher's poll loop.
nice_cmd=
command -v nice >/dev/null 2>&1 && nice_cmd="nice -n -5"

# Keep the donor loader and libraries together. A native build can omit lib/.
if [ -x "$runtime/lib/ld-linux-aarch64.so.1" ]; then
    if [ -f "$runtime/lib/dri/panfrost_dri.so" ] && [ ! -e "$runtime/lib/dri/rockchip_dri.so" ]; then
        # Earlier imports lacked the KMS render-only name used by the VOP.
        ln -s panfrost_dri.so "$runtime/lib/dri/rockchip_dri.so"
    fi
    export LD_LIBRARY_PATH="$runtime/lib:$extras/lib"
    # Arch-R's UAE4ARM core references Ogg/Vorbis without a DT_NEEDED entry.
    if [ "$1" = uae4arm ] && [ -r "$runtime/lib/libvorbisfile.so.3" ]; then
        export LD_PRELOAD="$runtime/lib/libvorbisfile.so.3${LD_PRELOAD:+:$LD_PRELOAD}"
    fi
    export LIBGL_DRIVERS_PATH="$runtime/lib/dri"
    # Mesa's KMS/GBM backend is shipped by the rootfs, not by the imported
    # runtime; without it EGL never initialises and the menu stays black.
    export GBM_BACKENDS_PATH="${GBM_BACKENDS_PATH:-/usr/lib/gbm}"
    export __EGL_VENDOR_LIBRARY_FILENAMES="$runtime/egl/50_mesa.json"
    export ALSOFT_DRIVERS=alsa
    export ALSA_CONFIG_DIR="$runtime/alsa"
    $nice_cmd "$runtime/lib/ld-linux-aarch64.so.1" "$runtime/retroarch" \
        --config "$cfg" --appendconfig "$hotkeys" -L "$core" "$rom"
else
    export GBM_BACKENDS_PATH="${GBM_BACKENDS_PATH:-/usr/lib/gbm}"
    $nice_cmd "$runtime/retroarch" --config "$cfg" --appendconfig "$hotkeys" \
        -L "$core" "$rom"
fi

rc=$?
[ -x "$boost" ] && "$boost" off
exit "$rc"
