CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic
CPPFLAGS ?= -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L

SRC := $(wildcard src/*.c)
OBJ := $(SRC:.c=.o)

saved: $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ)

%.o: %.c src
	$(CC) $(CFLAGS) $(CPPFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJ) saved

.PHONY: clean
