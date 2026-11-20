#include "dp_input.h"

#include <stdlib.h>
#include <unistd.h>

int __wrap_dp_input_open(struct dp_input *in)
{
    *in = (struct dp_input){ .fd = -1, .key_fd = -1, .axis_fd = -1, .ready = 1 };
    return 0;
}

enum dp_key __wrap_dp_input_poll(struct dp_input *in, int timeout_ms)
{
    (void)in;
    (void)timeout_ms;
    static int sent;
    const char *file = getenv("LAUNCH_CHORD_READY");
    if (!sent && file && access(file, F_OK) == 0) {
        sent = 1;
        return DP_KEY_MENU_BACK;
    }
    usleep(10000);
    return DP_KEY_NONE;
}
