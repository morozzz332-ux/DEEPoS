/* Link seams for testing the launcher boot path without a panel or a mount. */
#include <signal.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "dp_display.h"
#include "dp_input.h"

static int frame_presented;

int __wrap_dp_display_open(struct dp_display *display, const char *path)
{
    const char *mode = getenv("DEEPOS_TEST_FRAMEBUFFER");
    if (strcmp(mode, "missing") == 0)
        return -1;
    display->fake = path != NULL || strcmp(mode, "fake") == 0;
    return 0;
}

int __wrap_dp_display_present(struct dp_display *display, const struct dp_canvas *canvas)
{
    (void)display;
    (void)canvas;
    const char *mode = getenv("DEEPOS_TEST_FRAMEBUFFER");
    if (strcmp(mode, "crash") == 0)
        raise(SIGKILL);
    if (strcmp(mode, "fail") == 0)
        return -1;
    frame_presented = 1;
    return 0;
}

void __wrap_dp_display_close(struct dp_display *display)
{
    (void)display;
}

int __wrap_dp_input_open(struct dp_input *input)
{
    *input = (struct dp_input){ .fd = -1, .ready = 1 };
    return getenv("DEEPOS_TEST_PHYSICAL_KEYS") ? 0 : -1;
}

enum dp_key __wrap_dp_input_poll(struct dp_input *input, int timeout_ms)
{
    (void)input;
    (void)timeout_ms;
    static unsigned next;
    const enum dp_key keys[] = { DP_KEY_RIGHT, DP_KEY_RIGHT, DP_KEY_A, DP_KEY_QUIT };
    return next < sizeof(keys) / sizeof(keys[0]) ? keys[next++] : DP_KEY_QUIT;
}

int __real_access(const char *path, int mode);

int __wrap_access(const char *path, int mode)
{
    if (strcmp(path, "/run/deepos-boot") == 0 || strcmp(path, "/run/deepos-boot-report") == 0)
        return 0;
    return __real_access(path, mode);
}

int __wrap_execl(const char *path, const char *name, ...)
{
    va_list args;
    va_start(args, name);
    if (strcmp(path, "/bin/sh") == 0 && strcmp(name, "sh") == 0) {
        const char *flag = va_arg(args, void *);
        const char *command = va_arg(args, void *);
        va_end(args);
        if (!frame_presented || strcmp(flag, "-c") != 0 ||
            !strstr(command, "selfcheck.sh /flash/report/checks.txt --first-frame"))
            _exit(1);
        static const char refresh[] = "boot report refresh requested\n";
        _exit(write(STDOUT_FILENO, refresh, sizeof(refresh) - 1) < 0);
    }
    const char *expected[] = { "--state", "/data", "good", "--boot-ticket", "/run/deepos-boot" };
    int valid = frame_presented && strcmp(path, "/usr/bin/updatr") == 0 &&
                strcmp(name, "updatr") == 0;
    for (size_t i = 0; i < sizeof(expected) / sizeof(*expected); i++) {
        const char *arg = va_arg(args, void *);
        if (!arg || strcmp(arg, expected[i]) != 0) {
            valid = 0;
            break;
        }
    }
    va_end(args);
    if (!valid)
        _exit(1);
    static const char confirmed[] = "boot confirmation requested\n";
    _exit(write(STDOUT_FILENO, confirmed, sizeof(confirmed) - 1) < 0);
}
