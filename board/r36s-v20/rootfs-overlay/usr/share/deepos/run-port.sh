#!/bin/sh
# Enter the optional AArch64 PortMaster environment for the duration of a port.
set -eu
package=/opt/deepos/portmaster
runtime=$package/runtime
data=/data/portmaster
control=$data/PortMaster

[ "$#" -ge 1 ] || exit 2
if [ ! -x "$runtime/bin/bash" ]; then
    [ "$1" != --manager ] || exit 126
    exec /bin/sh "$@"
fi
mountpoint -q /data && mountpoint -q /storage || exit 6
mkdir -p "$data/home"
if [ ! -d "$control" ]; then
    staged=$(mktemp -d "$data/.package.XXXXXX")
    if ! cp -a "$package/PortMaster/." "$staged/" || ! mv -T "$staged" "$control"; then
        rm -rf "$staged"
        exit 1
    fi
fi

export HOME=$data/home
export XDG_CONFIG_HOME=$HOME/.config
export XDG_DATA_HOME=$data
export PATH="$runtime/bin:$PATH"
export PYTHONHOME=$runtime
export LD_LIBRARY_PATH=$runtime/lib
export LIBGL_DRIVERS_PATH=$runtime/lib/dri
export __EGL_VENDOR_LIBRARY_FILENAMES=$runtime/egl/50_mesa.json
export ALSA_CONFIG_DIR=$runtime/alsa
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-alsa}"
export PYSDL2_DLL_PATH=$runtime/lib
export SSL_CERT_FILE=$runtime/ca-bundle.crt
export controlfolder=$control
export HM_TOOLS_DIR=$data
export HM_PORTS_DIR=/storage/ports
export HM_SCRIPTS_DIR=$HM_PORTS_DIR

case "$1" in
    --manager|/storage/ports/PortMaster.sh)
        mkdir -p "$control/deepos"
        cp /usr/share/deepos/portmaster-hooks.sh "$control/deepos/launch_hooks.txt"
        exec /bin/bash -c 'source "$controlfolder/utils/pm_launch.txt" deepos'
        ;;
esac

exec /bin/bash "$@"
