# DEEPoS launcher - host build (the device build uses the same sources via
# board/r36s-v20 recipes; here we only need a native binary for tests).
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic -D_GNU_SOURCE
LDFLAGS ?=
SRC := $(wildcard src/*.c)
OBJ := $(SRC:.c=.o)
BIN := launcher

.PHONY: all clean test

all: $(BIN)

$(BIN): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDFLAGS)

src/%.o: src/%.c src/dp_canvas.h src/dp_font.h src/dp_model.h src/dp_theme.h src/dp_ui.h
	$(CC) $(CFLAGS) -c -o $@ $<

test: $(BIN)
	@echo "run: python tests/run.py"

clean:
	rm -f $(OBJ) $(BIN)
