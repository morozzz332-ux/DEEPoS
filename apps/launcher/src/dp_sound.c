/* Small one-shot tones on the console's ALSA PCM device. */
#include "dp_sound.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <unistd.h>
#include <sound/asound.h>

#define DP_SAMPLE_RATE 48000

static void pcm_value(struct snd_pcm_hw_params *p, unsigned param, unsigned value)
{
    struct snd_interval *interval = &p->intervals[param - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL];
    interval->min = interval->max = value;
    interval->integer = 1;
}

static int prepare_pcm(int fd)
{
    struct snd_pcm_hw_params p = { .rmask = UINT_MAX };
    p.masks[SNDRV_PCM_HW_PARAM_ACCESS].bits[0] = 1U << SNDRV_PCM_ACCESS_RW_INTERLEAVED;
    p.masks[SNDRV_PCM_HW_PARAM_FORMAT].bits[0] = 1U << SNDRV_PCM_FORMAT_S16_LE;
    p.masks[SNDRV_PCM_HW_PARAM_SUBFORMAT].bits[0] = 1U << SNDRV_PCM_SUBFORMAT_STD;
    for (unsigned i = 0; i <= SNDRV_PCM_HW_PARAM_LAST_INTERVAL - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL; i++)
        p.intervals[i].max = UINT_MAX;
    pcm_value(&p, SNDRV_PCM_HW_PARAM_CHANNELS, 2);
    pcm_value(&p, SNDRV_PCM_HW_PARAM_RATE, DP_SAMPLE_RATE);
    pcm_value(&p, SNDRV_PCM_HW_PARAM_PERIODS, 4);
    p.intervals[SNDRV_PCM_HW_PARAM_PERIOD_SIZE - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL].min = 128;
    if (ioctl(fd, (int)SNDRV_PCM_IOCTL_HW_PARAMS, &p) < 0)
        return -1;

    unsigned buffer = p.intervals[SNDRV_PCM_HW_PARAM_BUFFER_SIZE - SNDRV_PCM_HW_PARAM_FIRST_INTERVAL].min;
    if (!buffer)
        return -1;
    struct snd_pcm_sw_params sw = {
        .avail_min = 1, .start_threshold = 1, .stop_threshold = buffer, .boundary = buffer,
    };
    while (sw.boundary <= ((unsigned long)LONG_MAX - buffer) / 2)
        sw.boundary *= 2;
    if (ioctl(fd, (int)SNDRV_PCM_IOCTL_SW_PARAMS, &sw) < 0)
        return -1;
    return ioctl(fd, SNDRV_PCM_IOCTL_PREPARE);
}

static void play(int fd, enum dp_tone tone)
{
    const int periods[][2] = { { 71, 71 }, { 89, 57 }, { 71, 108 } };
    const int frames = tone == DP_TONE_TAB ? 864 : 1536;
    int16_t samples[1536 * 2];
    int phase = 0;
    for (int i = 0; i < frames; i++) {
        int period = periods[tone][i >= frames / 2];
        phase = (phase + 1) % period;
        int triangle = phase < period / 2 ? phase * 4 - period : 3 * period - phase * 4;
        int attack = i < 96 ? i : 96;
        int level = 1700 * attack / 96 * (frames - i) / frames;
        samples[2 * i] = samples[2 * i + 1] = (int16_t)(triangle * level / period);
    }
    if (fcntl(fd, F_SETFL, 0) < 0 || prepare_pcm(fd) < 0)
        return;
    int pos = 0;
    while (pos < frames) {
        struct snd_xferi write_frames = { .buf = samples + 2 * pos, .frames = frames - pos };
        if (ioctl(fd, (int)SNDRV_PCM_IOCTL_WRITEI_FRAMES, &write_frames) < 0 || write_frames.result <= 0)
            return;
        pos += (int)write_frames.result;
    }
    ioctl(fd, SNDRV_PCM_IOCTL_DRAIN);
}

static int is_playing(pid_t active)
{
    if (active <= 0)
        return 0;
    pid_t result;
    do {
        result = waitpid(active, NULL, WNOHANG);
    } while (result < 0 && errno == EINTR);
    return result == 0;
}

pid_t dp_sound_play(pid_t active, enum dp_tone tone)
{
    if (is_playing(active))
        return active;
    int fd = -1;
    for (int card = 0; card < 4 && fd < 0; card++) {
        char path[40];
        snprintf(path, sizeof(path), "/dev/snd/pcmC%dD0p", card);
        fd = open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    }
    if (fd < 0)
        return 0;
    pid_t child = fork();
    if (child == 0) {
        alarm(1);
        play(fd, tone);
        _exit(0);
    }
    close(fd);
    return child > 0 ? child : 0;
}

void dp_sound_stop(pid_t active)
{
    if (is_playing(active)) {
        kill(active, SIGTERM);
        while (waitpid(active, NULL, 0) < 0 && errno == EINTR) { }
    }
}
