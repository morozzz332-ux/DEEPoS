/* Host stand-in for /dev/input/event0: an evdev-like pipe that also answers the
 * ioctls dp_input_open uses to pick the right node. */
#include "dp_input.h"

#include <errno.h>
#include <fcntl.h>
#include <asm/ioctl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int event_pipe[2] = { -1, -1 };
static const char *device_name = "";
static unsigned char key_bits[KEY_MAX / 8 + 1];

int __wrap_open(const char *path, int flags, ...)
{
    (void)flags;
    if (strcmp(path, "/dev/input/event0") == 0)
        return dup(event_pipe[0]);
    errno = ENOENT;
    return -1;
}

int __wrap_ioctl(int fd, unsigned long request, ...)
{
    (void)fd;
    va_list args;
    va_start(args, request);
    void *buf = va_arg(args, void *);
    va_end(args);

    if (_IOC_TYPE(request) != 'E')
        goto unsupported;
    switch (_IOC_NR(request)) {
    case 0x06: { /* EVIOCGNAME */
        size_t len = _IOC_SIZE(request);
        memset(buf, 0, len);
        if (len > 1)
            strncpy(buf, device_name, len - 1);
        return 0;
    }
    case 0x20: { /* EVIOCGBIT(0) - event types: only EV_KEY matters here */
        size_t len = _IOC_SIZE(request);
        unsigned char *bits = buf;
        memset(bits, 0, len);
        if (len > EV_KEY / 8)
            bits[EV_KEY / 8] |= (unsigned char)(1u << (EV_KEY % 8));
        return 0;
    }
    case 0x21: { /* EVIOCGBIT(EV_KEY) */
        size_t len = _IOC_SIZE(request);
        memset(buf, 0, len);
        memcpy(buf, key_bits, len < sizeof(key_bits) ? len : sizeof(key_bits));
        return 0;
    }
    case 0x23: /* EVIOCGBIT(EV_ABS) */
        memset(buf, 0, _IOC_SIZE(request));
        *(unsigned char *)buf = (1 << ABS_X) | (1 << ABS_Y) | (1 << ABS_RX) | (1 << ABS_RY);
        return 0;
    case 0x40 + ABS_X:
    case 0x40 + ABS_Y:
    case 0x40 + ABS_RX:
    case 0x40 + ABS_RY:
        *(struct input_absinfo *)buf = (struct input_absinfo){ .minimum = 0, .maximum = 1023,
                                                              .value = 512, .flat = 10 };
        return 0;
    default:
        break;
    }

unsupported:
    errno = ENOTTY;
    return -1;
}

static void keys_reset(void)
{
    memset(key_bits, 0, sizeof(key_bits));
}

static void key_set(unsigned code)
{
    key_bits[code / 8] |= (unsigned char)(1u << (code % 8));
}

static int open_fake(const char *name)
{
    device_name = name;
    if (event_pipe[0] >= 0) {
        close(event_pipe[0]);
        close(event_pipe[1]);
        event_pipe[0] = event_pipe[1] = -1;
    }
    return pipe(event_pipe) < 0 || fcntl(event_pipe[0], F_SETFL, O_NONBLOCK) < 0;
}

static int check_key(struct dp_input *input, unsigned short code, unsigned value,
                     enum dp_key expected)
{
    struct input_event event = {.type = EV_KEY, .code = code, .value = value};
    if (write(event_pipe[1], &event, sizeof(event)) != (ssize_t)sizeof(event))
        return 1;
    enum dp_key actual = dp_input_poll(input, 0);
    if (actual == expected)
        return 0;
    fprintf(stderr, "%s code 0x%x value %u: expected %s, got %s\n", device_name, code,
            value, dp_key_name(expected), dp_key_name(actual));
    return 1;
}

static int check_axis(struct dp_input *input, unsigned short code, int value, enum dp_key expected)
{
    struct input_event event = {.type = EV_ABS, .code = code, .value = value};
    if (write(event_pipe[1], &event, sizeof(event)) != (ssize_t)sizeof(event))
        return 1;
    enum dp_key actual = dp_input_poll(input, 0);
    if (actual == expected)
        return 0;
    fprintf(stderr, "axis %u value %d: expected %s, got %s\n", code, value,
            dp_key_name(expected), dp_key_name(actual));
    return 1;
}

static int check_pad(const char *name, enum dp_key south, enum dp_key east, int vendor_dpad)
{
    keys_reset();
    if (vendor_dpad) {
        /* Arch-R's singleadc joypad reports the D-pad as BTN_DPAD_* and the
         * face buttons as BTN_EAST/SOUTH/WEST/NORTH. */
        key_set(BTN_DPAD_UP);
        key_set(BTN_DPAD_DOWN);
        key_set(BTN_DPAD_LEFT);
        key_set(BTN_DPAD_RIGHT);
    } else {
        key_set(KEY_UP);
        key_set(KEY_DOWN);
        key_set(KEY_LEFT);
        key_set(KEY_RIGHT);
    }
    key_set(BTN_SOUTH);
    key_set(BTN_EAST);
    key_set(BTN_TL);
    key_set(BTN_TR);
    key_set(BTN_TL2);
    key_set(BTN_TR2);
    key_set(BTN_SELECT);
    key_set(KEY_SELECT);
    key_set(BTN_START);
    if (open_fake(name) != 0)
        return 1;
    struct dp_input input;
    if (dp_input_open(&input) < 0) {
        fprintf(stderr, "%s: dp_input_open did not accept a real pad\n", name);
        return 1;
    }
    close(event_pipe[0]);
    int failed = 0;
    failed |= check_key(&input, BTN_SOUTH, 1, south);
    failed |= check_key(&input, BTN_EAST, 1, east);
    failed |= check_key(&input, BTN_DPAD_UP, 1, DP_KEY_UP);
    failed |= check_key(&input, BTN_DPAD_DOWN, 1, DP_KEY_DOWN);
    failed |= check_key(&input, BTN_DPAD_LEFT, 1, DP_KEY_LEFT);
    failed |= check_key(&input, BTN_DPAD_RIGHT, 1, DP_KEY_RIGHT);
    failed |= check_key(&input, BTN_SELECT, 1, DP_KEY_SELECT);
    failed |= check_key(&input, BTN_TL, 1, DP_KEY_L1);
    failed |= check_key(&input, BTN_TR, 1, DP_KEY_R1);
    failed |= check_key(&input, BTN_TL2, 1, DP_KEY_L2);
    failed |= check_key(&input, BTN_TR2, 1, DP_KEY_R2);
    failed |= check_key(&input, BTN_NORTH, 1, DP_KEY_X);
    failed |= check_key(&input, BTN_WEST, 1, DP_KEY_Y);
    failed |= check_key(&input, BTN_MODE, 1, DP_KEY_FN);
    failed |= check_key(&input, BTN_THUMBL, 1, DP_KEY_L3);
    failed |= check_key(&input, BTN_THUMBR, 1, DP_KEY_R3);
    failed |= check_key(&input, KEY_VOLUMEUP, 1, DP_KEY_VOL_UP);
    failed |= check_key(&input, KEY_VOLUMEDOWN, 1, DP_KEY_VOL_DOWN);
    failed |= check_key(&input, BTN_DPAD_DOWN, 2, DP_KEY_DOWN);
    failed |= check_key(&input, BTN_SOUTH, 2, DP_KEY_NONE);
    failed |= check_axis(&input, ABS_X, 540, DP_KEY_NONE);
    failed |= check_axis(&input, ABS_X, 1020, DP_KEY_RIGHT);
    failed |= check_axis(&input, ABS_X, 1000, DP_KEY_NONE);
    failed |= check_axis(&input, ABS_X, 510, DP_KEY_NONE);
    failed |= check_axis(&input, ABS_X, 0, DP_KEY_LEFT);
    failed |= check_axis(&input, ABS_RY, 20, DP_KEY_UP);
    failed |= check_key(&input, BTN_SELECT, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_START, 1, DP_KEY_START);
    failed |= check_key(&input, BTN_SELECT, 1, dp_key_from_name("select+start"));
    failed |= check_key(&input, BTN_START, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 1, DP_KEY_SELECT);
    failed |= check_key(&input, BTN_START, 1, dp_key_from_name("select+start"));
    failed |= check_key(&input, BTN_START, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 0, DP_KEY_NONE);
    input.game_only = 1;
    failed |= check_axis(&input, ABS_X, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SOUTH, 1, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 1, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 0, DP_KEY_NONE);
    failed |= check_key(&input, BTN_START, 1, DP_KEY_NONE);
    failed |= check_key(&input, BTN_SELECT, 1, DP_KEY_MENU_BACK);
    failed |= check_key(&input, KEY_VOLUMEUP, 1, DP_KEY_VOL_UP);
    dp_input_close(&input);
    close(event_pipe[1]);
    return failed;
}

static int check_reject(const char *name)
{
    keys_reset();
    key_set(KEY_ENTER);
    if (open_fake(name) != 0)
        return 1;
    struct dp_input input;
    int rc = dp_input_open(&input);
    if (rc == 0) {
        fprintf(stderr, "%s: dp_input_open accepted a node without a D-pad\n", name);
        dp_input_close(&input);
        close(event_pipe[1]);
        return 1;
    }
    fprintf(stderr, "%s: rejected as expected\n", name);
    close(event_pipe[0]);
    close(event_pipe[1]);
    return 0;
}

int main(void)
{
    int failed = check_pad("r36s_Gamepad", DP_KEY_B, DP_KEY_A, 1);
    failed |= check_pad("gpio-keys", DP_KEY_A, DP_KEY_B, 0);
    failed |= check_reject("keyboard");
    return failed;
}
