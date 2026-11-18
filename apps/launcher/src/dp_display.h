/* DEEPoS launcher - display output.
 *
 * On the device the kernel exposes a DRM fbdev (CONFIG_DRM_FBDEV_EMULATION) as
 * /dev/fb0 with a 16 bpp RGB565 buffer, so the launcher can blit the canvas with
 * a plain mmap - no libdrm, no EGL, no compositor.
 *
 * For host tests the same code can write into a regular file: when the ioctl
 * queries fail but a path was given explicitly, we fall back to 640x480x16 and
 * ftruncate the file, which makes the blit byte-comparable with the PPM render.
 */
#ifndef DP_DISPLAY_H
#define DP_DISPLAY_H

#include <stddef.h>

#include "dp_canvas.h"

struct dp_display {
    int fd;
    unsigned char *mem;
    size_t len;
    size_t offset;
    int w;
    int h;
    int bpp;
    int stride;
    int fake; /* 1 = file-backed test surface */
};

/* path == NULL means /dev/fb0. Returns 0 on success. */
int dp_display_open(struct dp_display *d, const char *path);
void dp_display_close(struct dp_display *d);

/* Blits the canvas into the mapped surface. Returns 0 on success. */
int dp_display_present(struct dp_display *d, const struct dp_canvas *cv);

#endif /* DP_DISPLAY_H */
