/* DEEPoS launcher - fbdev output (mmap + RGB565 blit). */
#include "dp_display.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

/* Minimum of the kernel fb API we need (avoids pulling in <linux/fb.h>). */
struct dp_fb_bitfield {
    unsigned int offset;
    unsigned int length;
    unsigned int msb_right;
};

struct dp_fb_var_screeninfo {
    unsigned int xres;
    unsigned int yres;
    unsigned int xres_virtual;
    unsigned int yres_virtual;
    unsigned int xoffset;
    unsigned int yoffset;
    unsigned int bits_per_pixel;
    unsigned int grayscale;
    struct dp_fb_bitfield red;
    struct dp_fb_bitfield green;
    struct dp_fb_bitfield blue;
    struct dp_fb_bitfield transp;
};

struct dp_fb_fix_screeninfo {
    char id[16];
    unsigned long smem_start;
    unsigned int smem_len;
    unsigned int type;
    unsigned int type_aux;
    unsigned int visual;
    unsigned short xpanstep;
    unsigned short ypanstep;
    unsigned short ywrapstep;
    unsigned int line_length;
};

#define DP_FBIOGET_VSCREENINFO 0x4600
#define DP_FBIOGET_FSCREENINFO 0x4602

#define DP_FB_FALLBACK_W 640
#define DP_FB_FALLBACK_H 480
#define DP_FB_FALLBACK_BPP 16

static int is_device_path(const char *path)
{
    struct stat st;
    return path && stat(path, &st) == 0 && !S_ISREG(st.st_mode);
}

int dp_display_open(struct dp_display *d, const char *path)
{
    const char *target = path ? path : "/dev/fb0";
    memset(d, 0, sizeof(*d));
    d->fd = -1;

    d->fd = open(target, O_RDWR);
    if (d->fd < 0 && !is_device_path(target))
        d->fd = open(target, O_RDWR | O_CREAT, 0644); /* test surface */
    if (d->fd < 0)
        return -1;

    struct dp_fb_var_screeninfo var;
    struct dp_fb_fix_screeninfo fix;
    memset(&var, 0, sizeof(var));
    memset(&fix, 0, sizeof(fix));

    int have_var = ioctl(d->fd, DP_FBIOGET_VSCREENINFO, &var) == 0;
    int have_fix = ioctl(d->fd, DP_FBIOGET_FSCREENINFO, &fix) == 0;

    if (have_var && var.xres > 0 && var.yres > 0 && var.bits_per_pixel > 0) {
        d->w = (int)var.xres;
        d->h = (int)var.yres;
        d->bpp = (int)var.bits_per_pixel;
        d->stride = have_fix && fix.line_length ? (int)fix.line_length : d->w * d->bpp / 8;
        d->len = (size_t)d->stride * (size_t)d->h;
        if (have_fix && fix.smem_len > d->len)
            d->len = fix.smem_len;
    } else if (!is_device_path(target)) {
        /* Test surface: a regular file stands in for the framebuffer. */
        d->w = DP_FB_FALLBACK_W;
        d->h = DP_FB_FALLBACK_H;
        d->bpp = DP_FB_FALLBACK_BPP;
        d->stride = d->w * d->bpp / 8;
        d->len = (size_t)d->stride * (size_t)d->h;
        d->fake = 1;
        if (ftruncate(d->fd, (off_t)d->len) != 0) {
            close(d->fd);
            d->fd = -1;
            return -1;
        }
    } else {
        close(d->fd);
        d->fd = -1;
        return -1;
    }

    d->mem = mmap(NULL, d->len, PROT_READ | PROT_WRITE, MAP_SHARED, d->fd, 0);
    if (d->mem == MAP_FAILED) {
        close(d->fd);
        d->mem = NULL;
        d->fd = -1;
        return -1;
    }
    return 0;
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
    unsigned char *row = d->mem + (size_t)y * (size_t)d->stride;
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
