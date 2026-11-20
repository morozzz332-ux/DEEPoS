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

# A 470 KiB SDL_GAMECONTROLLERCONFIG exceeds MAX_ARG_STRLEN, which makes every
# execve() in the port fail with E2BIG ("Argument list too long"). Trim before
# control.txt turns the file into an environment variable.
[ -x /usr/share/deepos/curate-controllerdb.sh ] &&
    /usr/share/deepos/curate-controllerdb.sh "$data" >/dev/null 2>&1 || true

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
# SDL dlopen()s libudev.so.1 and libEGL.so.1 by soname. Without them SDL_Init
# dies with SIGSEGV inside the kmsdrm driver and every port "just crashes";
# the rootfs ships both, so keep /usr/lib on the search path.
export LD_LIBRARY_PATH=$runtime/lib:/usr/lib
export LIBGL_DRIVERS_PATH=$runtime/lib/dri
# Mesa's KMS/GBM backend lives in /usr/lib/gbm (shipped by the rootfs): without
# it every EGL surface creation fails with "failed to open dri: dri_gbm.so".
export GBM_BACKENDS_PATH="${GBM_BACKENDS_PATH:-/usr/lib/gbm}"
export __EGL_VENDOR_LIBRARY_FILENAMES=$runtime/egl/50_mesa.json
export ALSA_CONFIG_DIR=$runtime/alsa
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-alsa}"
# A recompiled port can monopolise two cores; with the stock SDL buffer the ALSA
# thread misses its deadline and the speaker crackles. 8192 frames (~170 ms at
# 48 kHz) removed most of it on the device and costs nothing else.
export SDL_AUDIO_DEVICE_SAMPLE_FRAMES="${SDL_AUDIO_DEVICE_SAMPLE_FRAMES:-8192}"
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

# dArkOSRE boosts the clocks around every launch (perfmax/perfnorm). policy0 is
# already at "performance" here, so only the GPU needs it, plus a niceness bump:
# the launcher's own poll loop must not compete with the port's render thread.
/usr/local/bin/perf-boost.sh on
trap '/usr/local/bin/perf-boost.sh off' EXIT INT TERM
if [ -x /bin/nice ]; then
    nice -n -5 /bin/bash "$@"
else
    /bin/bash "$@"
fi
rc=$?
/usr/local/bin/perf-boost.sh off
exit "$rc"
