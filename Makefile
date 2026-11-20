# DEEPoS top-level orchestration.
# Host builds run in Docker (tests/ci/Dockerfile) so they work on any machine.
# Kernel and boot-chain builds use the cross toolchain image (tools/cross/Dockerfile).

DOCKER ?= docker
IMAGE  ?= deepos-build:local
CROSS_IMAGE ?= deepos-cross:local
PYTHON ?= python3
SIZE_MIB ?= 4096
IMG      ?= build/deepos-r36s-v20.img
KARCH  ?= linux-6.12.56

.PHONY: playdemo-test settings-test preflight preflight-test release release-test config-test help selftest-test fonts launcher modd saved updatr updatr render test modd-test saved-test launch-test modules-test image-test board-test boot-test kconfig-check verify-image docker-image docker-cross docker-test kernel uboot image-full image boot clean

help:
	@echo "make fonts        - regenerate bitmap glyph tables from the bundled Terminus fonts"
	@echo "make launcher     - build apps/launcher (native, needs cc + make)"
	@echo "make modd         - build apps/modd (native, needs cc + make)"
	@echo "make saved        - build apps/saved (native, needs cc + make)"
	@echo "make render       - render all screens to PPM (tests/out)"
	@echo "make test         - build + run the launcher test suite"
	@echo "make modd-test    - build + run the module supervisor tests"
	@echo "make saved-test   - build + run the save-store tests"
	@echo "make modules-test - run thermal/saves module protocol tests (docker)"
	@echo "make launch-test  - launcher -> modd hook -> emulator pipeline"
	@echo "make image-test   - build a small test image and check GPT + filesystems"
	@echo "make image        - build a full card image into build/"
	@echo "make docker-image - build the reproducible toolchain image"
	@echo "make docker-cross - build the aarch64 cross toolchain image"
	@echo "make board-test   - dtb, kernel/busybox config fragments, extlinux, rootfs builder"
	@echo "make boot-test    - BOOT tree assembler (mkboot) and A/B boot state (update)"
	@echo "make kconfig-check- merge linux.config into a real 6.12 kernel tree and verify"
	@echo "make kernel       - cross-build Image + board DTB into build/kernel"
	@echo "make uboot        - cross-build the Rockchip boot chain into build/uboot"
	@echo "make preflight    - GO/NO-GO check of kernel, dtb, boot tree, rootfs, loaders"
	@echo "make release      - write docs/RELEASE.md with sha256 of every artefact"
	@echo "make verify-image - verify the built image (GPT CRCs, loader, payloads) before flashing"
	@echo "make image-full   - full image with real kernel, DTB, boot chain and rootfs"
	@echo "make docker-test  - run every test suite inside the image (recommended)"

fonts:
	$(PYTHON) tools/gen-font.py

launcher:
	$(MAKE) -C apps/launcher

modd:
	$(MAKE) -C apps/modd

updatr:
	$(MAKE) -C apps/updatr

saved:
	$(MAKE) -C apps/saved

render: launcher
	sh tests/ci/render-all.sh "$(CURDIR)" "$(CURDIR)/tests/out"

test:
	$(PYTHON) tests/run.py

modd-test: modd
	$(PYTHON) tests/modd_test.py

modules-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/modules_test.py"

updatr-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/updatr && python3 tests/updatr_test.py && python3 tests/input_test.py && python3 tests/launcher_mod_test.py"

saved-test: saved
	$(PYTHON) tests/saved_test.py

docker-image:
	$(DOCKER) build -t $(IMAGE) -f tests/ci/Dockerfile .

docker-cross:
	$(DOCKER) build -t $(CROSS_IMAGE) -f tools/cross/Dockerfile .

docker-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/run.py && python3 tests/modd_test.py && python3 tests/saved_test.py && python3 tests/modules_test.py && python3 tests/image_test.py && python3 tests/board_test.py && python3 tests/boot_test.py"

launcher-mod-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher clean >/dev/null && make -C apps/launcher make -C apps/modd && python3 tests/launcher_mod_test.py"

launch-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher clean >/dev/null && make -C apps/launcher && make -C apps/modd && python3 tests/launch_test.py && python3 tests/modd_test.py"

display-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher clean >/dev/null && make -C apps/launcher && python3 tests/display_test.py"

selftest-test: docker-image
	$(DOCKER) run --rm --entrypoint /bin/bash -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher clean >/dev/null && make -C apps/launcher && python3 tests/selftest_test.py"

input-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher clean >/dev/null && make -C apps/launcher && python3 tests/input_test.py && python3 tests/launcher_mod_test.py"

playdemo-test:
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/playdemo && python3 tests/playdemo_test.py"

settings-test:
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/settings_test.py"

config-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "make -C apps/launcher >/dev/null && python3 tests/config_test.py"

board-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/board_test.py"

kconfig-check: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "sh tools/kconfig-check.sh"

boot-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/boot_test.py"

image-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/image_test.py"

kernel: docker-cross
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(CROSS_IMAGE) -c "sh tools/build-kernel.sh"

uboot: docker-cross
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(CROSS_IMAGE) -c "sh tools/build-uboot.sh"

# Version of the whole build (BOOT manifest, os-release, launcher banner). The
# repository VERSION file is the single source; override with make VERSION=...
VERSION ?= $(shell cat VERSION 2>/dev/null || echo 0.26-dev)
BOOT_EXTRA ?= board/r36s-v20/boot/README-FIRST.txt
# Board DTB: the one checked in under board/ is the stock tree with the speaker
# routed to the codec class-D stage (tools/dtb-sound-fix.py), because the tree
# built from board/dts is mainline and does not describe this panel/PLL setup.
BOARD_DTB ?= board/r36s-v20/boot/dtbs/rk3326-r36s-v20.dtb
KERNEL_DTB = $(if $(wildcard $(BOARD_DTB)),$(BOARD_DTB),build/kernel/rk3326-r36s-v20.dtb)
LOADER_DONOR ?=
DONOR_BIND = $(if $(LOADER_DONOR),--mount "type=bind,source=$(abspath $(LOADER_DONOR)),target=$(DONOR_PATH),readonly")
DONOR_PATH = /rockchip-donor$(suffix $(LOADER_DONOR))
LOADER_ARG = $(if $(LOADER_DONOR),--loader-donor $(DONOR_PATH),--loader build/uboot)
BOOT_SCRIPT_ARG = $(if $(LOADER_DONOR),--boot-script board/r36s-v20/boot/boot.cmd)

boot: docker-image
	@test -f build/kernel/Image || (echo "missing build/kernel/Image - run 'make kernel' first" >&2; exit 1)
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) \
		-c "python3 tools/mkboot.py --kernel build/kernel/Image \
			--dtb $(KERNEL_DTB) --out build/boot \
			--extlinux board/r36s-v20/boot/extlinux/extlinux.conf \
			--logo branding/deepos-boot.bmp \
			--extra $(BOOT_EXTRA) $(BOOT_SCRIPT_ARG) --version $(VERSION)"

image: image-full

# Full image: real kernel + DTB (build/kernel), boot chain (build/uboot) and the
# staged BOOT tree. Fails loudly when a piece is missing instead of silently
# producing an unbootable card.
verify-image: docker-image
	@echo "==> verifying $(IMG) before writing it to a card"
	$(DOCKER) run --rm -v "$(CURDIR):/w" $(DONOR_BIND) -w /w $(IMAGE) \
		-c "python3 tools/verify-image.py $(LOADER_ARG) $(IMG)"

image-full: boot
	@test -f build/kernel/Image || (echo "missing build/kernel/Image - run 'make kernel' first" >&2; exit 1)
	@test -n "$(LOADER_DONOR)" || test -f build/uboot/idbloader.img || (echo "missing build/uboot/idbloader.img - run 'make uboot' first" >&2; exit 1)
	$(DOCKER) run --rm -v "$(CURDIR):/w" $(DONOR_BIND) -w /w $(IMAGE) -c "mkdir -p build/data && cp board/r36s-v20/data/emulators.toml build/data/emulators.toml && python3 tools/mkimage.py --out $(IMG) --size-mib $(SIZE_MIB) --boot build/boot --sys-a build/rootfs.squashfs --data build/data $(LOADER_ARG)"
	$(MAKE) verify-image

clean:
	$(MAKE) -C apps/launcher clean
	$(MAKE) -C apps/modd clean
	$(MAKE) -C apps/saved clean
	rm -rf tests/out

preflight:
	$(DOCKER) run --rm -v "$(CURDIR):/w" $(DONOR_BIND) -w /w $(IMAGE) -c "python3 tools/preflight.py --root /w $(LOADER_ARG) --image $(IMG)"

release:
	$(DOCKER) run --rm -v "$(CURDIR):/w" $(DONOR_BIND) -w /w $(IMAGE) -c "python3 tools/release.py --root . $(LOADER_ARG) --image $(IMG)"

release-test:
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/release_test.py"

preflight-test:
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/preflight_test.py"

