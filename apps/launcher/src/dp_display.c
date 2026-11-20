/* DEEPoS launcher - fbdev output (mmap + RGB565 blit). */
#include "dp_display.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/kd.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#define DP_FB_FALLBACK_W 640
#define DP_FB_FALLBACK_H 480
#define DP_FB_FALLBACK_BPP 16

static int valid_channel(struct fb_bitfield channel, unsigned bpp)
{
    return channel.length <= 16 && channel.offset <= bpp - channel.length &&
           channel.msb_right == 0;
}

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
        if (!var.xres || !var.yres || !fix.line_length || fix.type != FB_TYPE_PACKED_PIXELS ||
            (var.bits_per_pixel != 16 && var.bits_per_pixel != 24 && var.bits_per_pixel != 32))
            goto fail;
        if (!var.red.length || !var.green.length || !var.blue.length ||
            !valid_channel(var.red, var.bits_per_pixel) ||
            !valid_channel(var.green, var.bits_per_pixel) ||
            !valid_channel(var.blue, var.bits_per_pixel) ||
            (var.transp.length && !valid_channel(var.transp, var.bits_per_pixel)))
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
        d->red = var.red.offset;
        d->green = var.green.offset;
        d->blue = var.blue.offset;
        d->alpha = var.transp.length ? var.transp.offset : 0;
        d->red_bits = var.red.length;
        d->green_bits = var.green.length;
        d->blue_bits = var.blue.length;
        d->alpha_bits = var.transp.length;
    } else if (path && fstat(d->fd, &st) == 0 && S_ISREG(st.st_mode)) {
        /* Test surface: a regular file stands in for the framebuffer. */
        d->w = DP_FB_FALLBACK_W;
        d->h = DP_FB_FALLBACK_H;
        d->bpp = DP_FB_FALLBACK_BPP;
        d->stride = d->w * d->bpp / 8;
        d->len = (size_t)d->stride * (size_t)d->h;
        d->fake = 1;
        d->red = 11;
        d->green = 5;
        d->red_bits = d->blue_bits = 5;
        d->green_bits = 6;
        if (ftruncate(d->fd, (off_t)d->len) != 0)
            goto fail;
    } else {
        goto fail;
    }

    d->mem = mmap(NULL, d->len, PROT_READ | PROT_WRITE, MAP_SHARED, d->fd, 0);
    if (d->mem == MAP_FAILED)
        goto fail;
    if (!d->fake) {
        /* Keep fbcon from repainting over the menu or the boot splash. */
        int tty = open("/dev/tty0", O_RDWR | O_NOCTTY | O_CLOEXEC);
        if (tty >= 0) {
            ioctl(tty, KDSETMODE, KD_GRAPHICS);
            close(tty);
        }
        ioctl(d->fd, FBIOBLANK, FB_BLANK_UNBLANK);
    }
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

static unsigned channel(unsigned value, unsigned max, unsigned bits, unsigned offset)
{
    return (value * ((1U << bits) - 1) / max) << offset;
}

int dp_display_present(struct dp_display *d, const struct dp_canvas *cv)
{
    if (!d->mem || d->w <= 0 || d->h <= 0)
        return -1;
    int w = cv->w < d->w ? cv->w : d->w;
    int h = cv->h < d->h ? cv->h : d->h;
    int native = d->bpp == 16 && d->red == 11 && d->green == 5 && d->blue == 0 &&
                 d->red_bits == 5 && d->green_bits == 6 && d->blue_bits == 5;
    int bytes = d->bpp / 8;
    unsigned alpha = ((1U << d->alpha_bits) - 1) << d->alpha;
    for (int y = 0; y < h; y++) {
        unsigned char *dst = d->mem + d->offset + (size_t)y * (size_t)d->stride;
        const uint16_t *src = cv->px + (size_t)y * (size_t)cv->w;
        if (native) {
            memcpy(dst, src, (size_t)w * sizeof(*src));
            continue;
        }
        for (int x = 0; x < w; x++) {
            uint16_t p = src[x];
            unsigned value = alpha | channel(p >> 11, 31, d->red_bits, d->red) |
                             channel((p >> 5) & 63, 63, d->green_bits, d->green) |
                             channel(p & 31, 31, d->blue_bits, d->blue);
            for (int b = 0; b < bytes; b++)
                *dst++ = (unsigned char)(value >> (b * 8));
        }
    }
    if (d->fake && fflush(NULL) != 0)
        return -1;
    return 0;
}
