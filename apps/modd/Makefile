# DEEPoS modd (host prototype)
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L
BIN := modd
SRC := src/modd.c src/dp_module.c src/dp_json.c
HDR := src/dp_module.h src/dp_json.h

all: $(BIN)

$(BIN): $(SRC) $(HDR)
	$(CC) $(CFLAGS) -o $@ $(SRC)

clean:
	rm -f $(BIN)

.PHONY: all clean
