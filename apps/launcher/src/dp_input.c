/* DEEPoS launcher - evdev input backend and key-name helpers.
 *
 * We deliberately avoid <linux/input.h>: the build image is musl/alpine and the
 * userland is static, so the evdev ABI constants we need are declared here.
 */
#include "dp_input.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
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
#define KEY_VOLUMEDOWN 114
#define KEY_VOLUMEUP 115
#define KEY_FN 0x1d0

#define BTN_SOUTH 0x130
#define BTN_EAST 0x131
#define BTN_NORTH 0x133
#define BTN_WEST 0x134
#define BTN_TL 0x136
#define BTN_TR 0x137
#define BTN_TL2 0x138
#define BTN_TR2 0x139
#define BTN_SELECT 0x13a
#define BTN_MODE 0x13c
#define BTN_THUMBL 0x13d
#define BTN_THUMBR 0x13e
#define BTN_DPAD_UP 0x220
#define BTN_DPAD_DOWN 0x221
#define BTN_DPAD_LEFT 0x222
#define BTN_DPAD_RIGHT 0x223

#define KEY_MAX 0x2ff
#define KEY_BYTES ((KEY_MAX + 8) / 8)

#define EVIOCGNAME(len) _IOC(_IOC_READ, 'E', 0x06, len)
#define EVIOCGBIT(ev, len) ((int)_IOC(_IOC_READ, 'E', 0x20 + (ev), len))
#define EVIOCGKEY(len) ((int)_IOC(_IOC_READ, 'E', 0x18, len))
#define EV_ABS 3
#define EVIOCGABS(axis) ((int)_IOR('E', 0x40 + (axis), struct dp_absinfo))

struct dp_absinfo {
    int value, minimum, maximum, fuzz, flat, resolution;
};

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
    {"l2", DP_KEY_L2},       {"r2", DP_KEY_R2},
    {"sel", DP_KEY_SELECT},  {"select", DP_KEY_SELECT},
    {"start", DP_KEY_START}, {"quit", DP_KEY_QUIT},
    {"fn", DP_KEY_FN},      {"l3", DP_KEY_L3},
    {"r3", DP_KEY_R3},      {"vol+", DP_KEY_VOL_UP},
    {"vol-", DP_KEY_VOL_DOWN},
    {"select+start", DP_KEY_MENU_BACK},
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

const char *dp_input_name(const struct dp_input *in)
{
    return in && in->name[0] ? in->name : "none";
}

static int bit_test(const unsigned char *bits, unsigned bit)
{
    return (bits[bit / 8] >> (bit % 8)) & 1;
}

/* A gamepad must report at least the D-pad or a face button. This rules out
 * power switches, accelerometers and the ADC joystick driver node (which only
 * reports absolute axes). */
static int pad_capabilities(int fd)
{
    unsigned char evbits[8] = { 0 };
    unsigned char keys[KEY_BYTES] = { 0 };
    if (ioctl(fd, EVIOCGBIT(0, sizeof(evbits)), evbits) < 0)
        return -1;
    if (!bit_test(evbits, EV_KEY))
        return -1;
    if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) < 0)
        return -1;
    int arrows = (bit_test(keys, KEY_UP) || bit_test(keys, BTN_DPAD_UP)) +
                 (bit_test(keys, KEY_DOWN) || bit_test(keys, BTN_DPAD_DOWN)) +
                 (bit_test(keys, KEY_LEFT) || bit_test(keys, BTN_DPAD_LEFT)) +
                 (bit_test(keys, KEY_RIGHT) || bit_test(keys, BTN_DPAD_RIGHT));
    int face = bit_test(keys, BTN_SOUTH) + bit_test(keys, BTN_EAST) +
               bit_test(keys, BTN_TL) + bit_test(keys, BTN_SELECT);
    if (arrows == 0)
        return -1;
    if (arrows < 4 && face == 0)
        return -1;
    return arrows * 2 + face;
}

static int name_bonus(const char *name)
{
    if (strcasecmp(name, "r36s_Gamepad") == 0)
        return 50; /* legacy vendor DTB on Arch-R */
    if (strcasestr(name, "gpio-keys") || strcasestr(name, "gamepad") ||
        strcasestr(name, "deepos"))
        return 20;
    return 0;
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
    case BTN_TL2:
        return DP_KEY_L2;
    case BTN_TR2:
        return DP_KEY_R2;
    case KEY_SELECT:
    case BTN_SELECT:
        return DP_KEY_SELECT;
    case KEY_START:
        return DP_KEY_START;
    case BTN_MODE:
    case KEY_FN:
        return DP_KEY_FN;
    case BTN_THUMBL:
        return DP_KEY_L3;
    case BTN_THUMBR:
        return DP_KEY_R3;
    case KEY_VOLUMEUP:
        return DP_KEY_VOL_UP;
    case KEY_VOLUMEDOWN:
        return DP_KEY_VOL_DOWN;
    default:
        return DP_KEY_NONE;
    }
}

static int is_direction(enum dp_key key)
{
    return key == DP_KEY_UP || key == DP_KEY_DOWN ||
           key == DP_KEY_LEFT || key == DP_KEY_RIGHT;
}

static int has_volume_keys(int fd)
{
    unsigned char bits[KEY_BYTES] = { 0 };
    if (ioctl(fd, (int)EVIOCGBIT(EV_KEY, sizeof(bits)), bits) < 0)
        return 0;
    return bit_test(bits, KEY_VOLUMEUP) && bit_test(bits, KEY_VOLUMEDOWN);
}

static int axis_percent(const struct dp_axis *axis, int value)
{
    long long span = (long long)axis->max - axis->min;
    if (value <= axis->min)
        return -100;
    if (value >= axis->max)
        return 100;
    return (int)((((long long)value - axis->min) * 200 + span / 2) / span - 100);
}

static int open_axes(struct dp_input *in, int fd)
{
    unsigned char bits[8] = { 0 };
    if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(bits)), bits) < 0)
        return 0;
    /* Standard gamepad axes, the vendor Z/RZ pair, or ADC indices 0..3. */
    int codes[DP_STICK_AXES] = { 0, 1, 3, 4 };
    if (!bit_test(bits, 3) || !bit_test(bits, 4)) {
        codes[2] = 2;
        codes[3] = bit_test(bits, 5) ? 5 : 3;
    }
    int count = 0;
    for (int i = 0; i < DP_STICK_AXES; i++) {
        struct dp_absinfo info;
        int code = codes[i];
        in->axes[i] = (struct dp_axis){ .code = -1 };
        if (!bit_test(bits, (unsigned)code) || ioctl(fd, EVIOCGABS(code), &info) < 0 ||
            info.maximum <= info.minimum)
            continue;
        struct dp_axis *axis = &in->axes[i];
        *axis = (struct dp_axis){ .code = code, .min = info.minimum, .max = info.maximum };
        axis->value = axis_percent(axis, info.value);
        count++;
    }
    return count;
}

static enum dp_key input_axis(struct dp_input *in, const struct dp_input_event *ev)
{
    for (int i = 0; i < DP_STICK_AXES; i++) {
        struct dp_axis *axis = &in->axes[i];
        if (axis->code != ev->code || axis->max <= axis->min)
            continue;
        int previous = axis->value;
        axis->value = axis_percent(axis, ev->value);
        if (in->inspect)
            return previous != axis->value ? DP_KEY_INPUT_STATE : DP_KEY_NONE;
        int direction = axis->value >= 45 ? 1 : axis->value <= -45 ? -1 : 0;
        if (!direction && abs(axis->value) > 25)
            return DP_KEY_NONE;
        int changed = axis->direction != direction;
        axis->direction = direction;
        if (!changed || !direction || !(in->stick_mask & (1u << (i / 2))))
            return DP_KEY_NONE;
        if (in->axes[i ^ 1].direction)
            return DP_KEY_NONE;
        if (i % 2)
            return direction > 0 ? DP_KEY_DOWN : DP_KEY_UP;
        return direction > 0 ? DP_KEY_RIGHT : DP_KEY_LEFT;
    }
    return DP_KEY_NONE;
}

static enum dp_key input_button(struct dp_input *in, const struct dp_input_event *ev)
{
    enum dp_key key = map_code(ev->code, in->swap_ab);
    if (key == DP_KEY_NONE)
        return key;
    unsigned bit = 1u << key;
    if (ev->value == 0) {
        in->held &= ~bit;
        return in->inspect ? DP_KEY_INPUT_STATE : DP_KEY_NONE;
    }
    if (ev->value == 2)
        return is_direction(key) && !in->inspect ? key : DP_KEY_NONE;
    if (ev->value != 1)
        return DP_KEY_NONE;
    in->held |= bit;
    in->seen |= bit;
    if (key == DP_KEY_SELECT || key == DP_KEY_START) {
        const unsigned chord = (1u << DP_KEY_SELECT) | (1u << DP_KEY_START);
        if ((in->held & chord) == chord)
            return DP_KEY_MENU_BACK;
    }
    return key;
}

int dp_input_open(struct dp_input *in)
{
    memset(in, 0, sizeof(*in));
    in->fd = -1;
    in->key_fd = -1;
    in->axis_fd = -1;
    in->stick_mask = 3;
    int best = -1, best_index = -1, best_score = 0;
    for (int i = 0; i < 32; i++) {
        char path[64];
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0)
            continue;
        int caps = pad_capabilities(fd);
        if (caps < 0) {
            close(fd);
            continue;
        }
        char name[DP_INPUT_NAME] = { 0 };
        if (ioctl(fd, (int)EVIOCGNAME(sizeof(name) - 1), name) < 0)
            memset(name, 0, sizeof(name));
        int score = caps + name_bonus(name);
        if (score > best_score) {
            if (best >= 0)
                close(best);
            best = fd;
            best_index = i;
            best_score = score;
            snprintf(in->name, sizeof(in->name), "%s", name);
            in->swap_ab = strcasecmp(name, "r36s_Gamepad") == 0;
        } else {
            close(fd);
        }
    }
    if (best < 0)
        return -1;
    int combined_axes = open_axes(in, best);
    for (int i = 0; i < 32; i++) {
        if (i == best_index)
            continue;
        char path[64];
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0)
            continue;
        char name[DP_INPUT_NAME] = { 0 };
        ioctl(fd, (int)EVIOCGNAME(sizeof(name) - 1), name);
        if (!combined_axes && in->axis_fd < 0 && strcasestr(name, "joystick") && open_axes(in, fd)) {
            in->axis_fd = fd;
            continue;
        }
        if (has_volume_keys(fd) && (in->key_fd < 0 ||
            (strcasecmp(name, "adc-keys") == 0 && strcasecmp(in->key_name, "adc-keys") != 0))) {
            if (in->key_fd >= 0)
                close(in->key_fd);
            in->key_fd = fd;
            snprintf(in->key_name, sizeof(in->key_name), "%s", name);
            continue;
        }
        close(fd);
    }
    const char *force = getenv("DEEPOS_SWAP_AB");
    if (best >= 0 && force && force[0] == '1')
        in->swap_ab = 1;
    in->fd = best;
    in->ready = 1;
    return 0;
}

void dp_input_close(struct dp_input *in)
{
    if (in->fd >= 0)
        close(in->fd);
    if (in->key_fd >= 0)
        close(in->key_fd);
    if (in->axis_fd >= 0)
        close(in->axis_fd);
    in->fd = -1;
    in->key_fd = -1;
    in->axis_fd = -1;
    in->ready = 0;
}

int dp_input_recovery_held(void)
{
    struct dp_input in;
    if (dp_input_open(&in) < 0)
        return 0;
    unsigned char keys[KEY_BYTES] = { 0 };
    int held = in.fd >= 0 && ioctl(in.fd, EVIOCGKEY(sizeof(keys)), keys) >= 0 &&
               bit_test(keys, KEY_START) && (bit_test(keys, KEY_SELECT) || bit_test(keys, BTN_SELECT));
    dp_input_close(&in);
    return held;
}

enum dp_key dp_input_poll(struct dp_input *in, int timeout_ms)
{
    if (!in->ready)
        return DP_KEY_NONE;
    struct pollfd fds[] = {
        { .fd = in->key_fd, .events = POLLIN },
        { .fd = in->fd, .events = POLLIN },
        { .fd = in->game_only ? -1 : in->axis_fd, .events = POLLIN },
    };
    if (poll(fds, sizeof(fds) / sizeof(fds[0]), timeout_ms) <= 0)
        return DP_KEY_NONE;
    for (unsigned i = 0; i < sizeof(fds) / sizeof(fds[0]); i++) {
        if (fds[i].revents & (POLLERR | POLLHUP | POLLNVAL)) {
            if (i == 1) {
                in->ready = 0;
                in->lost = 1;
                return DP_KEY_NONE;
            }
            close(fds[i].fd);
            if (i == 0)
                in->key_fd = -1;
            else {
                in->axis_fd = -1;
                memset(in->axes, 0, sizeof(in->axes));
                if (in->inspect)
                    return DP_KEY_INPUT_STATE;
            }
            continue;
        }
        if (!(fds[i].revents & POLLIN))
            continue;
        struct dp_input_event ev;
        while (read(fds[i].fd, &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
            enum dp_key key = DP_KEY_NONE;
            if (ev.type == EV_ABS && i != 0 && !in->game_only)
                key = input_axis(in, &ev);
            if (ev.type == EV_KEY && i != 2) {
                int volume = ev.code == KEY_VOLUMEUP || ev.code == KEY_VOLUMEDOWN;
                int chord = ev.code == BTN_SELECT || ev.code == KEY_SELECT || ev.code == KEY_START;
                if (volume || (i == 1 && (!in->game_only || chord)))
                    key = input_button(in, &ev);
                if (in->game_only && !volume && key != DP_KEY_MENU_BACK)
                    key = DP_KEY_NONE;
            }
            if (key == DP_KEY_NONE)
                continue;
            in->last_us = (unsigned long long)ev.sec * 1000000ULL +
                          (unsigned long long)(ev.usec < 0 ? 0 : ev.usec);
            return key;
        }
    }
    return DP_KEY_NONE;
}

int dp_input_scan(const char *path)
{
    if (!path)
        return -1;
    FILE *out = fopen(path, "w");
    if (!out)
        return -1;

    for (int i = 0; i < 32; i++) {
        char dev[64];
        snprintf(dev, sizeof(dev), "/dev/input/event%d", i);
        int fd = open(dev, O_RDONLY | O_NONBLOCK);
        if (fd < 0)
            continue;
        char name[DP_INPUT_NAME] = { 0 };
        if (ioctl(fd, (int)EVIOCGNAME(sizeof(name) - 1), name) < 0)
            memset(name, 0, sizeof(name));
        unsigned char evbits[8] = { 0 };
        unsigned char absbits[8] = { 0 };
        unsigned char keys[KEY_BYTES] = { 0 };
        ioctl(fd, EVIOCGBIT(0, sizeof(evbits)), evbits);
        ioctl(fd, EVIOCGBIT(0x03, sizeof(absbits)), absbits);

        int arrows = 0, face = 0, keybits = 0;
        if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) >= 0) {
            arrows = (bit_test(keys, KEY_UP) || bit_test(keys, BTN_DPAD_UP)) +
                     (bit_test(keys, KEY_DOWN) || bit_test(keys, BTN_DPAD_DOWN)) +
                     (bit_test(keys, KEY_LEFT) || bit_test(keys, BTN_DPAD_LEFT)) +
                     (bit_test(keys, KEY_RIGHT) || bit_test(keys, BTN_DPAD_RIGHT));
            face = bit_test(keys, BTN_SOUTH) + bit_test(keys, BTN_EAST) +
                   bit_test(keys, BTN_NORTH) + bit_test(keys, BTN_WEST) +
                   bit_test(keys, BTN_TL) + bit_test(keys, BTN_TR) +
                   bit_test(keys, BTN_SELECT) + bit_test(keys, KEY_START);
            for (unsigned b = 0; b <= KEY_MAX; b++)
                keybits += bit_test(keys, b);
        }
        int absbits_n = 0;
        for (unsigned b = 0; b < 64; b++)
            absbits_n += bit_test(absbits, b);

        fprintf(out, "event%d name=%s arrows=%d face=%d keys=%d abs=%d evbits=",
                i, name[0] ? name : "-", arrows, face, keybits, absbits_n);
        for (unsigned b = 0; b < sizeof(evbits); b++)
            fprintf(out, "%02x", evbits[b]);
        fputc('\n', out);
        close(fd);
    }

    FILE *mods = fopen("/proc/modules", "r");
    if (mods) {
        char line[512];
        while (fgets(line, sizeof(line), mods)) {
            if (strstr(line, "joypad"))
                fprintf(out, "module %s", line);
        }
        fclose(mods);
    }
    FILE *ver = fopen("/proc/version", "r");
    if (ver) {
        char line[512];
        if (fgets(line, sizeof(line), ver))
            fprintf(out, "kernel %s", line);
        fclose(ver);
    }
    fclose(out);
    return 0;
}

int dp_input_probe(struct dp_input *in, int seconds, const char *path)
{
    if (!in || in->fd < 0 || !path)
        return -1;
    FILE *out = fopen(path, "a");
    if (!out)
        return -1;

    unsigned char evbits[8] = { 0 };
    unsigned char absbits[8] = { 0 };
    unsigned char keys[KEY_BYTES] = { 0 };
    int have_ev = ioctl(in->fd, EVIOCGBIT(0, sizeof(evbits)), evbits) >= 0;
    int have_abs = ioctl(in->fd, EVIOCGBIT(0x03, sizeof(absbits)), absbits) >= 0;
    int have_keys = ioctl(in->fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) >= 0;

    fprintf(out, "device=%s\nswap_ab=%d\n", dp_input_name(in), in->swap_ab);
    if (have_ev) {
        fprintf(out, "evbits=");
        for (unsigned i = 0; i < sizeof(evbits); i++)
            fprintf(out, "%02x", evbits[i]);
        fputc('\n', out);
    }
    if (have_keys) {
        fprintf(out, "keycodes=");
        for (unsigned code = 0; code <= KEY_MAX; code++) {
            if (!bit_test(keys, code))
                continue;
            enum dp_key k = map_code(code, in->swap_ab);
            if (k != DP_KEY_NONE)
                fprintf(out, "0x%x:(%s) ", code, dp_key_name(k));
            else
                fprintf(out, "0x%x ", code);
        }
        fputc('\n', out);
    }
    if (have_abs) {
        fprintf(out, "absbits=");
        for (unsigned i = 0; i < sizeof(absbits); i++)
            fprintf(out, "%02x", absbits[i]);
        fputc('\n', out);
    }

    int ticks = seconds > 0 ? seconds * 5 : 5;
    struct pollfd pfd = { .fd = in->fd, .events = POLLIN };
    while (ticks-- > 0) {
        int rc = poll(&pfd, 1, 200);
        if (rc < 0) {
            if (errno == EINTR)
                continue;
            break;
        }
        if (rc == 0)
            continue;
        if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            fputs("lost\n", out);
            break;
        }
        for (;;) {
            struct dp_input_event ev;
            ssize_t n = read(in->fd, &ev, sizeof(ev));
            if (n != (ssize_t)sizeof(ev))
                break;
            enum dp_key k = ev.type == EV_KEY ? map_code(ev.code, in->swap_ab)
                                              : DP_KEY_NONE;
            fprintf(out, "t=%ld.%06ld type=%u code=0x%x value=%d key=%s\n",
                    ev.sec, ev.usec, ev.type, ev.code, ev.value,
                    k == DP_KEY_NONE ? "-" : dp_key_name(k));
        }
    }
    fclose(out);
    return 0;
}
