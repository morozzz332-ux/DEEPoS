# DEEPoS build/test environment (host-side).
# Used by `tools/test.ps1` and CI: builds the launcher for x86_64 with the
# same strict flags as the device build and runs the Python test suite.
FROM alpine:3.20

# alsa-lib-dev brings <sound/asound.h>: the launcher talks to the ALSA control
# interface directly, so the host build needs the same header the device build
# gets from the cross image.
RUN apk add --no-cache build-base make python3 py3-pillow bash dosfstools mtools squashfs-tools e2fsprogs exfatprogs dtc bc flex bison perl git u-boot-tools linux-headers alsa-lib-dev tzdata

WORKDIR /w
ENTRYPOINT ["/bin/sh"]
