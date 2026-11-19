/* DEEPoS launcher - key input abstraction.
 *
 * On the device the launcher reads /dev/input/eventN (gpio-keys + adc-joystick
 * declared in the board DTS). On a host (tests, CI) there is no evdev, so the
 * same state machine is driven by synthetic keys through --keys.
 */
#ifndef DP_INPUT_H
#define DP_INPUT_H

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
    DP_KEY_SELECT,
    DP_KEY_START,
    DP_KEY_QUIT
};

struct dp_input {
    int fd;
    int ready;
    int swap_ab;
};

/* Open the first input device that looks like the console's keypad. */
int dp_input_open(struct dp_input *in);
void dp_input_close(struct dp_input *in);

/* Block up to timeout_ms; returns DP_KEY_NONE on timeout. */
enum dp_key dp_input_poll(struct dp_input *in, int timeout_ms);

/* Parse a textual key name ("UP", "down", "A", "SEL", "START", "QUIT"). */
enum dp_key dp_key_from_name(const char *name);
const char *dp_key_name(enum dp_key key);

#endif /* DP_INPUT_H */
