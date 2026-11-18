# DEEPoS top-level orchestration.
# Host builds run in Docker (tests/ci/Dockerfile) so they work on any machine.

DOCKER ?= docker
IMAGE  ?= deepos-build:local
PYTHON ?= python3

.PHONY: help fonts launcher modd saved render test modd-test saved-test modules-test image-test board-test docker-image docker-test image clean

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
	@echo "make board-test   - dtb, kernel/busybox config fragments, extlinux, rootfs builder"
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

docker-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/run.py && python3 tests/modd_test.py && python3 tests/saved_test.py && python3 tests/modules_test.py && python3 tests/image_test.py && python3 tests/board_test.py"

board-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/board_test.py"

image-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/image_test.py"

image: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tools/mkimage.py --out build/deepos-r36s-v20.img --boot build/boot --sys-a build/rootfs --data build/data"

clean:
	$(MAKE) -C apps/launcher clean
	$(MAKE) -C apps/modd clean
	$(MAKE) -C apps/saved clean
	rm -rf tests/out
