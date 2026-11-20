# DEEPoS launcher - host build (the device build uses the same sources via
# board/r36s-v20 recipes; here we only need a native binary for tests).
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic -D_GNU_SOURCE
# The version lives in the repository VERSION file so the UI, os-release and the
# BOOT manifest cannot drift apart.
DP_VERSION ?= $(shell cat ../../VERSION 2>/dev/null || echo 0.0-dev)
# A separate -D flag: CFLAGS may arrive from the caller (tools/build-userland.sh),
# and command-line variables would silently drop a "CFLAGS +=" assignment.
DEFS := -DDP_VERSION='"$(DP_VERSION)"'
LDFLAGS ?=
SRC := $(wildcard src/*.c)
OBJ := $(SRC:.c=.o)
BIN := launcher

.PHONY: all clean test

all: $(BIN)

$(BIN): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDFLAGS)

src/%.o: src/%.c src/dp_canvas.h src/dp_font.h src/dp_model.h src/dp_sound.h src/dp_theme.h src/dp_ui.h
	$(CC) $(CFLAGS) $(DEFS) -c -o $@ $<

src/dp_clock.o: src/dp_clock.h src/dp_zones.def

test: $(BIN)
	@echo "run: python tests/run.py"

clean:
	rm -f $(OBJ) $(BIN)
