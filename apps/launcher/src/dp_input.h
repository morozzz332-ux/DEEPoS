/* DEEPoS launcher - key input abstraction.
 *
 * On the device the launcher reads /dev/input/eventN (gpio-keys + adc-joystick
 * declared in the board DTS). On a host (tests, CI) there is no evdev, so the
 * same state machine is driven by synthetic keys through --keys.
 */
#ifndef DP_INPUT_H
#define DP_INPUT_H

#define DP_INPUT_NAME 64

enum dp_key {
    DP_KEY_NONE = 0,
    DP_KEY_UP,
    DP_KEY_DOWN,
    DP_KEY_LEFT,
    DP_KEY_RIGHT,
    DP_KEY_A,
    DP_KEY_B,
    DP_KEY_X,
    DP_KEY_Y,
    DP_KEY_L1,
    DP_KEY_R1,
    DP_KEY_L2,
    DP_KEY_R2,
    DP_KEY_SELECT,
    DP_KEY_START,
    DP_KEY_QUIT,
    DP_KEY_FN,
    DP_KEY_L3,
    DP_KEY_R3,
    DP_KEY_VOL_UP,
    DP_KEY_VOL_DOWN
};

struct dp_input {
    int fd;
    /* Volume rocker sits on the adc-keys node, a different evdev device than
     * the gamepad. Keeping a second descriptor is cheaper than a daemon. */
    int key_fd;
    int ready;      /* 1 while the device is open and has not disappeared */
    int swap_ab;    /* legacy vendor DTB labels the face buttons the other way */
    int lost;       /* 1 after the device disappeared (POLLERR/POLLHUP) */
    char name[DP_INPUT_NAME];
    char key_name[DP_INPUT_NAME];
    /* CLOCK_REALTIME stamp of the last delivered key, microseconds. The
     * launcher subtracts its own clock to measure input-to-present latency. */
    unsigned long long last_us;
};

/* Open the input device with the best gamepad score (capabilities, not just
 * the name). Returns 0 on success. */
int dp_input_open(struct dp_input *in);

/* Diagnostic: dump the device capabilities and every raw event received during
 * `seconds` to `path`. Used from a one-shot boot probe (/flash/INPUT.PROBE). */
int dp_input_probe(struct dp_input *in, int seconds, const char *path);

/* Diagnostic: list every /dev/input/event* node with its name and the key
 * capabilities we care about, plus the loaded joypad modules. Creates `path`. */
int dp_input_scan(const char *path);
void dp_input_close(struct dp_input *in);

/* Block up to timeout_ms; returns DP_KEY_NONE on timeout.
 *
 * Kernel autorepeat (value 2) is accepted for the four directions only, so
 * holding the D-pad scrolls a list but holding A never fires twice. */
enum dp_key dp_input_poll(struct dp_input *in, int timeout_ms);

const char *dp_input_name(const struct dp_input *in);

/* Parse a textual key name ("UP", "down", "A", "SEL", "START", "QUIT"). */
enum dp_key dp_key_from_name(const char *name);
const char *dp_key_name(enum dp_key key);

#endif /* DP_INPUT_H */
