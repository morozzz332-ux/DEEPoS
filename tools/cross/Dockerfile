# Cross-build image for DEEPoS kernel/DTB/U-Boot work.
#
# Ubuntu is used here (not Alpine) because it packages a ready
# aarch64-linux-gnu toolchain plus the host tools the kernel build needs.
#
#   docker build -t deepos-cross:local -f tools/cross/Dockerfile .
#   docker run --rm -v "<repo>:/w" -w /w deepos-cross:local -c "sh tools/build-kernel.sh"
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential bc bison flex libssl-dev libelf-dev \
        gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu \
        gcc-arm-none-eabi \
        python3 python3-pillow xz-utils wget ca-certificates \
        device-tree-compiler dosfstools mtools squashfs-tools \
        e2fsprogs exfatprogs make git rsync file \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /w
ENTRYPOINT ["/bin/sh"]
