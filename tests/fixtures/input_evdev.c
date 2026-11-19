#include "dp_input.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int event_pipe[2];
static const char *device_name;

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
    (void)request;
    va_list args;
    va_start(args, request);
    char *name = va_arg(args, char *);
    strcpy(name, device_name);
    va_end(args);
    return 0;
}

static int check_key(struct dp_input *input, unsigned short code, enum dp_key expected)
{
    struct input_event event = {.type = EV_KEY, .code = code, .value = 1};
    if (write(event_pipe[1], &event, sizeof(event)) != (ssize_t)sizeof(event))
        return 1;
    enum dp_key actual = dp_input_poll(input, 0);
    if (actual == expected)
        return 0;
    fprintf(stderr, "%s code 0x%x: expected %s, got %s\n",
            device_name, code, dp_key_name(expected), dp_key_name(actual));
    return 1;
}

static int check_pad(const char *name, enum dp_key south, enum dp_key east)
{
    device_name = name;
    if (pipe(event_pipe) < 0 || fcntl(event_pipe[0], F_SETFL, O_NONBLOCK) < 0)
        return 1;
    struct dp_input input;
    if (dp_input_open(&input) < 0 || close(event_pipe[0]) < 0)
        return 1;
    int failed = 0;
    failed |= check_key(&input, BTN_SOUTH, south);
    failed |= check_key(&input, BTN_EAST, east);
    failed |= check_key(&input, BTN_DPAD_UP, DP_KEY_UP);
    failed |= check_key(&input, BTN_DPAD_DOWN, DP_KEY_DOWN);
    failed |= check_key(&input, BTN_DPAD_LEFT, DP_KEY_LEFT);
    failed |= check_key(&input, BTN_DPAD_RIGHT, DP_KEY_RIGHT);
    failed |= check_key(&input, BTN_SELECT, DP_KEY_SELECT);
    dp_input_close(&input);
    close(event_pipe[1]);
    return failed;
}

int main(void)
{
    int failed = check_pad("r36s_Gamepad", DP_KEY_B, DP_KEY_A);
    failed |= check_pad("gamepad", DP_KEY_A, DP_KEY_B);
    return failed;
}
