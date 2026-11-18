# DEEPoS top-level orchestration.
# Host builds run in Docker (tests/ci/Dockerfile) so they work on any machine.

DOCKER ?= docker
IMAGE  ?= deepos-build:local
PYTHON ?= python3

.PHONY: help fonts launcher render test docker-image docker-test image clean

help:
	@echo "make fonts        - regenerate bitmap fonts from tools/fonts/DejaVuSansMono.ttf"
	@echo "make launcher     - build apps/launcher (native, needs cc + make)"
	@echo "make render       - render all screens to PPM (tests/out)"
	@echo "make test         - build + run the test suite"
	@echo "make docker-image - build the reproducible toolchain image"
	@echo "make docker-test  - run the test suite inside the image (recommended)"

fonts:
	$(PYTHON) tools/gen-font.py

launcher:
	$(MAKE) -C apps/launcher

render: launcher
	sh tests/ci/render-all.sh "$(CURDIR)" "$(CURDIR)/tests/out"

test:
	$(PYTHON) tests/run.py

docker-image:
	$(DOCKER) build -t $(IMAGE) -f tests/ci/Dockerfile .

docker-test: docker-image
	$(DOCKER) run --rm -v "$(CURDIR):/w" -w /w $(IMAGE) -c "python3 tests/run.py"

image: docker-image

clean:
	$(MAKE) -C apps/launcher clean
	rm -rf tests/out
