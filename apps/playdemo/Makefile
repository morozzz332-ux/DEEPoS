CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L -D_GNU_SOURCE
LAUNCHER = ../launcher/src

SRC = src/main.c $(LAUNCHER)/dp_canvas.c $(LAUNCHER)/dp_display.c $(LAUNCHER)/dp_input.c
HDR = $(LAUNCHER)/dp_canvas.h $(LAUNCHER)/dp_display.h $(LAUNCHER)/dp_input.h \
      $(LAUNCHER)/dp_theme.h $(LAUNCHER)/dp_font.h $(LAUNCHER)/dp_font_small.h

playdemo: $(SRC) $(HDR)
	$(CC) $(CFLAGS) -I$(LAUNCHER) -o $@ $(SRC) $(LAUNCHER)/dp_font.c $(LAUNCHER)/dp_font_small.c

clean:
	rm -f playdemo

.PHONY: clean
