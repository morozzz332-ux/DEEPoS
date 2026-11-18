# DEEPoS top-level orchestration.
# Host builds run in Docker (tests/ci/Dockerfile) so they work on any machine.
# Kernel and boot-chain builds use the cross toolchain image (tools/cross/Dockerfile).

DOCKER ?= docker
IMAGE  ?= deepos-build:local
CROSS_IMAGE ?= deepos-cross:local
PYTHON ?= python3
KARCH  ?= linux-6.12.56

.PHONY: help fonts launcher modd saved render test modd-test saved-test modules-test image-test board-test boot-test kconfig-check docker-image docker-cross docker-test kernel uboot image-full image clean

help:
	@echo "make fonts        - regenerate bitmap fonts from tools/fonts/DejaVuSansMono.ttf"
	@echo "make launcher     - build apps/launcher (native, needs cc + make)"
	@echo "make modd         - build apps/modd (native, needs cc + make)"
	@echo "make saved        - build apps/saved (native, needs cc + make)"
	@echo "make render       - render all screens to PPM (tests/out)"
	@echo "make test         - build + run the launcher test suite"
	@echo "make modd-test    - build + run the module supervisor tests"
	@echo "make saved-test   - build + run the save-store tests"
	@echo "make modules-test - run thermal/saves module protocol tests (docker)"
	@echo "make image-test   - build a small test image and check GPT + filesystems"
	@echo "make image        - build a full card image into build/"
	@echo "make docker-image - build the reproducible toolchain image"
	@echo "make docker-cross - build the aarch64 cross toolchain image"
	@echo "make board-test   - dtb, kernel/busybox config fragments, extlinux, rootfs builder"
	@echo "make boot-test    - BOOT tree assembler (mkboot) and A/B boot state (update)"
	@echo "make kconfig-check- merge linux.config into a real 6.12 kernel tree and verify"
	@echo "make kernel       - cross-build Image + board DTB into build/kernel"
	@echo "make uboot        - cross-build the Rockchip boot chain into build/uboot"
	@echo "make image-full   - full image with real kernel, DTB, boot chain and rootfs"
	@echo "make docker-test  - run every test suite inside the image (recommended)"

fonts:
	$(PYTHON) tools/gen-font.py

launcher:
	$(MAKE) -C apps/launcher

modd:
	$(MAKE) -C apps/modd

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

saved-test: saved
	$(PYTHON) tests/saved_test.py

docker-image:
	$(DOCKER) build -t $(IMAGE) -f tests/ci/Dockerfile .

docker-cross:
	$(DOCKER) build -t $(CROSS_IMAGE) -f tools/cross/Dockerfile .

docker-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/run.py && python3 tests/modd_test.py && python3 tests/saved_test.py && python3 tests/modules_test.py && python3 tests/image_test.py && python3 tests/board_test.py && python3 tests/boot_test.py"

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

image: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tools/mkimage.py --out build/deepos-r36s-v20.img --size-mib $(SIZE_MIB) --boot build/boot --sys-a build/rootfs.squashfs --data build/data"

# Full image: real kernel + DTB (build/kernel), boot chain (build/uboot) and the
# staged BOOT tree. Fails loudly when a piece is missing instead of silently
# producing an unbootable card.
image-full: docker-image
	@test -f build/kernel/Image || (echo "missing build/kernel/Image - run 'make kernel' first" >&2; exit 1)
	@test -f build/uboot/idbloader.img || (echo "missing build/uboot/idbloader.img - run 'make uboot' first" >&2; exit 1)
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tools/mkimage.py --out build/deepos-r36s-v20.img --size-mib $(SIZE_MIB) --boot build/boot --sys-a build/rootfs.squashfs --data build/data --loader build/uboot"

clean:
	$(MAKE) -C apps/launcher clean
	$(MAKE) -C apps/modd clean
	$(MAKE) -C apps/saved clean
	rm -rf tests/out
