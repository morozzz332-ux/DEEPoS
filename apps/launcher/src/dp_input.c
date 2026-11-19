/* DEEPoS launcher - evdev input backend and key-name helpers.
 *
 * We deliberately avoid <linux/input.h>: the build image is musl/alpine and the
 * userland is static, so the evdev ABI constants we need are declared here.
 */
#include "dp_input.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define EV_SYN 0x00
#define EV_KEY 0x01

#define KEY_ESC 1
#define KEY_ENTER 28
#define KEY_UP 103
#define KEY_LEFT 105
#define KEY_RIGHT 106
#define KEY_DOWN 108
#define KEY_SELECT 0x161
#define KEY_START 0x13b

#define BTN_SOUTH 0x130
#define BTN_EAST 0x131
#define BTN_NORTH 0x133
#define BTN_WEST 0x134
#define BTN_TL 0x136
#define BTN_TR 0x137
#define BTN_SELECT 0x13a
#define BTN_DPAD_UP 0x220
#define BTN_DPAD_DOWN 0x221
#define BTN_DPAD_LEFT 0x222
#define BTN_DPAD_RIGHT 0x223

#define EVIOCGNAME(len) _IOC(_IOC_READ, 'E', 0x06, len)

struct dp_input_event {
    long sec;
    long usec;
    unsigned short type;
    unsigned short code;
    int value;
};

static const struct {
    const char *name;
    enum dp_key key;
} KEY_NAMES[] = {
    {"up", DP_KEY_UP},       {"down", DP_KEY_DOWN},
    {"left", DP_KEY_LEFT},   {"right", DP_KEY_RIGHT},
    {"a", DP_KEY_A},         {"b", DP_KEY_B},
    {"x", DP_KEY_X},         {"y", DP_KEY_Y},
    {"l1", DP_KEY_L1},       {"r1", DP_KEY_R1},
    {"sel", DP_KEY_SELECT},  {"select", DP_KEY_SELECT},
    {"start", DP_KEY_START}, {"quit", DP_KEY_QUIT},
};

const char *dp_key_name(enum dp_key key)
{
    for (unsigned i = 0; i < sizeof(KEY_NAMES) / sizeof(KEY_NAMES[0]); i++)
        if (KEY_NAMES[i].key == key)
            return KEY_NAMES[i].name;
    return "none";
}

enum dp_key dp_key_from_name(const char *name)
{
    if (!name)
        return DP_KEY_NONE;
    for (unsigned i = 0; i < sizeof(KEY_NAMES) / sizeof(KEY_NAMES[0]); i++)
        if (strcasecmp(KEY_NAMES[i].name, name) == 0)
            return KEY_NAMES[i].key;
    return DP_KEY_NONE;
}

enum pad_priority { PAD_OTHER = 1, PAD_CONSOLE, PAD_V20 };

static int looks_like_pad(int fd)
{
    char name[128] = {0};
    if (ioctl(fd, (int)EVIOCGNAME(sizeof(name) - 1), name) < 0)
        return 0;
    if (strcasecmp(name, "r36s_Gamepad") == 0)
        return PAD_V20;
    if (strcasestr(name, "r36s") || strcasestr(name, "deepos") ||
        strcasestr(name, "gamepad") || strcasestr(name, "gpio-keys"))
        return PAD_CONSOLE;
    return PAD_OTHER;
}

static enum dp_key map_code(unsigned int code, int swap_ab)
{
    switch (code) {
    case BTN_SOUTH:
        return swap_ab ? DP_KEY_B : DP_KEY_A;
    case BTN_EAST:
        return swap_ab ? DP_KEY_A : DP_KEY_B;
    case BTN_NORTH:
        return DP_KEY_X;
    case BTN_WEST:
        return DP_KEY_Y;
    case KEY_UP:
    case BTN_DPAD_UP:
        return DP_KEY_UP;
    case KEY_DOWN:
    case BTN_DPAD_DOWN:
        return DP_KEY_DOWN;
    case KEY_LEFT:
    case BTN_DPAD_LEFT:
        return DP_KEY_LEFT;
    case KEY_RIGHT:
    case BTN_DPAD_RIGHT:
        return DP_KEY_RIGHT;
    case KEY_ENTER:
        return DP_KEY_A;
    case KEY_ESC:
        return DP_KEY_B;
    case BTN_TL:
        return DP_KEY_L1;
    case BTN_TR:
        return DP_KEY_R1;
    case KEY_SELECT:
    case BTN_SELECT:
        return DP_KEY_SELECT;
    case KEY_START:
        return DP_KEY_START;
    default:
        return DP_KEY_NONE;
    }
}

int dp_input_open(struct dp_input *in)
{
    in->fd = -1;
    in->ready = 0;
    in->swap_ab = 0;
    int best = -1, best_score = 0;
    for (int i = 0; i < 32; i++) {
        char path[64];
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0)
            continue;
        int score = looks_like_pad(fd);
        if (score > best_score) {
            if (best >= 0)
                close(best);
            best = fd;
            best_score = score;
            if (score == PAD_V20)
                break;
        } else {
            close(fd);
        }
    }
    if (best >= 0) {
        in->fd = best;
        in->ready = 1;
        in->swap_ab = best_score == PAD_V20;
        return 0;
    }
    return -1;
}

void dp_input_close(struct dp_input *in)
{
    if (in->ready && in->fd >= 0)
        close(in->fd);
    in->fd = -1;
    in->ready = 0;
}

enum dp_key dp_input_poll(struct dp_input *in, int timeout_ms)
{
    (void)timeout_ms;
    if (!in->ready)
        return DP_KEY_NONE;
    for (;;) {
        struct dp_input_event ev;
        ssize_t n = read(in->fd, &ev, sizeof(ev));
        if (n != (ssize_t)sizeof(ev))
            return DP_KEY_NONE;
        if (ev.type != EV_KEY || ev.value != 1)
            continue;
        enum dp_key k = map_code(ev.code, in->swap_ab);
        if (k != DP_KEY_NONE)
            return k;
    }
}
