/* DEEPoS launcher - fbdev output (mmap + RGB565 blit). */
#include "dp_display.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define DP_FB_FALLBACK_W 640
#define DP_FB_FALLBACK_H 480
#define DP_FB_FALLBACK_BPP 16

int dp_display_open(struct dp_display *d, const char *path)
{
    const char *target = path ? path : "/dev/fb0";
    memset(d, 0, sizeof(*d));
    d->fd = -1;

    d->fd = open(target, O_RDWR | O_CLOEXEC);
    if (d->fd < 0 && path && errno == ENOENT)
        d->fd = open(target, O_RDWR | O_CREAT | O_CLOEXEC, 0644);
    if (d->fd < 0)
        return -1;

    struct fb_var_screeninfo var;
    struct fb_fix_screeninfo fix;
    struct stat st;
    if (ioctl(d->fd, FBIOGET_VSCREENINFO, &var) == 0 &&
        ioctl(d->fd, FBIOGET_FSCREENINFO, &fix) == 0) {
        if (!var.xres || !var.yres || !fix.line_length ||
            (var.bits_per_pixel != 16 && var.bits_per_pixel != 24 && var.bits_per_pixel != 32))
            goto fail;
        size_t pixels_end = ((size_t)var.xoffset + var.xres) * (var.bits_per_pixel / 8);
        size_t frame_end = ((size_t)var.yoffset + var.yres - 1) * fix.line_length + pixels_end;
        if (pixels_end > fix.line_length || frame_end > fix.smem_len)
            goto fail;
        d->w = (int)var.xres;
        d->h = (int)var.yres;
        d->bpp = (int)var.bits_per_pixel;
        d->stride = (int)fix.line_length;
        d->len = fix.smem_len;
        d->offset = (size_t)var.yoffset * fix.line_length + (size_t)var.xoffset * (var.bits_per_pixel / 8);
    } else if (path && fstat(d->fd, &st) == 0 && S_ISREG(st.st_mode)) {
        /* Test surface: a regular file stands in for the framebuffer. */
        d->w = DP_FB_FALLBACK_W;
        d->h = DP_FB_FALLBACK_H;
        d->bpp = DP_FB_FALLBACK_BPP;
        d->stride = d->w * d->bpp / 8;
        d->len = (size_t)d->stride * (size_t)d->h;
        d->fake = 1;
        if (ftruncate(d->fd, (off_t)d->len) != 0)
            goto fail;
    } else {
        goto fail;
    }

    d->mem = mmap(NULL, d->len, PROT_READ | PROT_WRITE, MAP_SHARED, d->fd, 0);
    if (d->mem == MAP_FAILED)
        goto fail;
    return 0;

fail:
    dp_display_close(d);
    return -1;
}

void dp_display_close(struct dp_display *d)
{
    if (d->mem && d->mem != MAP_FAILED)
        munmap(d->mem, d->len);
    if (d->fd >= 0)
        close(d->fd);
    d->mem = NULL;
    d->fd = -1;
}

static void put_pixel(struct dp_display *d, int x, int y, uint16_t p)
{
    unsigned char *row = d->mem + d->offset + (size_t)y * (size_t)d->stride;
    switch (d->bpp) {
    case 16: {
        uint16_t *dst = (uint16_t *)(void *)(row + (size_t)x * 2);
        *dst = p;
        break;
    }
    case 32: {
        unsigned r = (unsigned)((p >> 11) & 0x1F) << 3;
        unsigned g = (unsigned)((p >> 5) & 0x3F) << 2;
        unsigned b = (unsigned)(p & 0x1F) << 3;
        uint32_t v = (r << 16) | (g << 8) | b;
        uint32_t *dst = (uint32_t *)(void *)(row + (size_t)x * 4);
        *dst = v;
        break;
    }
    default: {
        unsigned char *dst = row + (size_t)x * 3;
        dst[0] = (unsigned char)(((p >> 11) & 0x1F) << 3);
        dst[1] = (unsigned char)(((p >> 5) & 0x3F) << 2);
        dst[2] = (unsigned char)((p & 0x1F) << 3);
        break;
    }
    }
}

int dp_display_present(struct dp_display *d, const struct dp_canvas *cv)
{
    if (!d->mem || d->w <= 0 || d->h <= 0)
        return -1;
    int w = cv->w < d->w ? cv->w : d->w;
    int h = cv->h < d->h ? cv->h : d->h;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++)
            put_pixel(d, x, y, cv->px[(size_t)y * (size_t)cv->w + (size_t)x]);
    if (d->fake && fflush(NULL) != 0)
        return -1;
    return 0;
}
