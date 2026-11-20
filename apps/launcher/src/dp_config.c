/* DEEPoS launcher - persistent settings, applied without a compositor. */
#define _POSIX_C_SOURCE 200809L

#include "dp_config.h"

#include <fcntl.h>
#include <glob.h>
#include <sys/ioctl.h>
#include <sound/asound.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DP_CFG_LINE 256

static const char *const pref_keys[DP_PREF_COUNT] = {
    "menu_sounds", "video_smooth", "fps_show", "integer_scale",
};

void dp_config_init(struct dp_config *cfg)
{
    cfg->brightness = 0;
    cfg->volume = 0;
    cfg->profile[0] = '\0';
    memset(cfg->prefs, 0, sizeof(cfg->prefs));
}

static int valid_profile(const char *value)
{
    return strcmp(value, "eco") == 0 || strcmp(value, "balanced") == 0 ||
           strcmp(value, "max") == 0;
}

static char *trim(char *s)
{
    while (*s == ' ' || *s == '\t') {
        s++;
    }
    size_t n = strlen(s);
    while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\n' ||
                 s[n - 1] == '\r')) {
        s[--n] = '\0';
    }
    return s;
}

int dp_config_set(struct dp_config *cfg, const char *kv)
{
    char buf[DP_CFG_LINE];
    snprintf(buf, sizeof(buf), "%s", kv);
    char *eq = strchr(buf, '=');
    if (!eq || eq == buf) {
        return -2;
    }
    *eq = '\0';
    char *key = trim(buf);
    char *val = trim(eq + 1);
    if (key[0] == '\0' || val[0] == '\0') {
        return -2;
    }

    if (strcmp(key, "brightness") == 0 || strcmp(key, "volume") == 0) {
        char *end = NULL;
        long n = strtol(val, &end, 10);
        int max = (key[0] == 'b') ? DP_CONFIG_BRIGHTNESS_MAX : DP_CONFIG_VOLUME_MAX;
        if (!end || end == val || *end != '\0' || n < 1 || n > max) {
            return -2;
        }
        if (key[0] == 'b') {
            cfg->brightness = (int)n;
        } else {
            cfg->volume = (int)n;
        }
        return 1;
    }
    if (strcmp(key, "profile") == 0) {
        if (!valid_profile(val) || strlen(val) >= DP_CONFIG_PROFILE_LEN) {
            return -2;
        }
        snprintf(cfg->profile, sizeof(cfg->profile), "%s", val);
        return 1;
    }
    for (int i = 0; i < DP_PREF_COUNT; i++) {
        if (strcmp(key, pref_keys[i]) != 0)
            continue;
        if (strcmp(val, "inherit") == 0)
            cfg->prefs[i] = 0;
        else if (strcmp(val, "on") == 0)
            cfg->prefs[i] = 1;
        else if (strcmp(val, "off") == 0)
            cfg->prefs[i] = 2;
        else
            return -2;
        return 1;
    }
    return 0;
}

int dp_config_load(struct dp_config *cfg, const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        return 0;
    }
    char line[DP_CFG_LINE];
    int rc = 0;
    while (fgets(line, sizeof(line), f)) {
        char *hash = strchr(line, '#');
        if (hash) {
            *hash = '\0';
        }
        char *p = line;
        while (*p == ' ' || *p == '\t') {
            p++;
        }
        size_t n = strlen(p);
        while (n && (p[n - 1] == '\n' || p[n - 1] == '\r' || p[n - 1] == ' ' ||
                     p[n - 1] == '\t')) {
            p[--n] = '\0';
        }
        if (n == 0) {
            continue;
        }
        int applied = dp_config_set(cfg, p);
        if (applied == -2) {
            rc = -2;
        }
    }
    fclose(f);
    return rc;
}

int dp_config_save(const struct dp_config *cfg, const char *path)
{
    char tmp[512];
    if (snprintf(tmp, sizeof(tmp), "%s.tmp.XXXXXX", path) >= (int)sizeof(tmp)) {
        return -1;
    }
    int fd = mkstemp(tmp);
    if (fd < 0)
        return -1;
    FILE *f = fdopen(fd, "w");
    if (!f) {
        close(fd);
        unlink(tmp);
        return -1;
    }
    fprintf(f, "# DEEPoS settings\n");
    fprintf(f, "brightness = %d\n", cfg->brightness);
    fprintf(f, "volume = %d\n", cfg->volume);
    fprintf(f, "profile = %s\n", cfg->profile[0] ? cfg->profile : "balanced");
    for (int i = 0; i < DP_PREF_COUNT; i++) {
        if (cfg->prefs[i])
            fprintf(f, "%s = %s\n", pref_keys[i], cfg->prefs[i] == 1 ? "on" : "off");
    }
    if (fflush(f) != 0 || fsync(fileno(f)) != 0) {
        fclose(f);
        unlink(tmp);
        return -1;
    }
    if (fclose(f) != 0) {
        unlink(tmp);
        return -1;
    }
    if (rename(tmp, path) != 0) {
        unlink(tmp);
        return -1;
    }
    return 0;
}

void dp_config_retroarch(const struct dp_config *cfg)
{
    static const char *const keys[DP_PREF_COUNT] = {
        [DP_PREF_SMOOTH] = "video_smooth",
        [DP_PREF_FPS] = "fps_show",
        [DP_PREF_INTEGER] = "video_scale_integer",
    };
    for (int i = 0; i < DP_PREF_COUNT; i++) {
        if (keys[i] && cfg->prefs[i])
            printf("%s = \"%s\"\n", keys[i], cfg->prefs[i] == 1 ? "true" : "false");
    }
}

static int write_number(const char *path, long value)
{
    if (access(path, W_OK) != 0)
        return 0;
    FILE *f = fopen(path, "w");
    if (!f)
        return 0;
    int ok = fprintf(f, "%ld\n", value) > 0;
    return fclose(f) == 0 && ok;
}

static long read_number(const char *path)
{
    long value = -1;
    FILE *f = fopen(path, "r");
    if (f) {
        if (fscanf(f, "%ld", &value) != 1)
            value = -1;
        fclose(f);
    }
    return value;
}

static int apply_backlight(const char *dir, int percent, long fallback)
{
    char path[512];
    if (snprintf(path, sizeof(path), "%s/max_brightness", dir) >= (int)sizeof(path))
        return 0;
    long maximum = read_number(path);
    if (maximum <= 0)
        maximum = fallback;
    if (maximum <= 0 || maximum > 65535)
        return 0;
    long raw = percent * maximum / 100;
    snprintf(path, sizeof(path), "%s/brightness", dir);
    return write_number(path, raw > 0 ? raw : 1);
}

int dp_config_apply_brightness(const char *prefix, int percent)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/class/backlight/*", prefix ? prefix : "/sys");
    glob_t devices = {0};
    int applied = 0;
    if (glob(path, 0, NULL, &devices) == 0) {
        for (size_t i = 0; i < devices.gl_pathc && !applied; i++)
            applied = apply_backlight(devices.gl_pathv[i], percent, 0);
    }
    globfree(&devices);
    if (prefix && !applied) {
        const char *names[] = {"deepos-bl", "backlight", "pwm-backlight"};
        for (size_t i = 0; i < sizeof(names) / sizeof(names[0]) && !applied; i++) {
            snprintf(path, sizeof(path), "%s/backlight/%s", prefix, names[i]);
            applied = apply_backlight(path, percent, 45);
        }
    }
    return applied;
}

int dp_config_apply_volume(const char *prefix, int percent)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/class/sound/card0/controlC0/volume_percent",
             prefix ? prefix : "/sys");
    if (write_number(path, percent))
        return 1;
    snprintf(path, sizeof(path), "%s/devices/platform/ff400000.i2s/sound/card0/volume_percent",
             prefix ? prefix : "/sys");
    if (write_number(path, percent))
        return 1;
    if (prefix)
        return 0;

    for (int card = 0; card < 8; card++) {
        snprintf(path, sizeof(path), "/dev/snd/controlC%d", card);
        int fd = open(path, O_RDWR | O_CLOEXEC);
        if (fd < 0)
            continue;
        struct snd_ctl_elem_info info = {0};
        info.id.iface = SNDRV_CTL_ELEM_IFACE_MIXER;
        snprintf((char *)info.id.name, sizeof(info.id.name), "Master Playback Volume");
        int ok = 0;
        if (ioctl(fd, (int)SNDRV_CTL_IOCTL_ELEM_INFO, &info) == 0 &&
            info.type == SNDRV_CTL_ELEM_TYPE_INTEGER && info.count > 0 &&
            info.count <= 128 && (info.access & SNDRV_CTL_ELEM_ACCESS_WRITE)) {
            struct snd_ctl_elem_value value = { .id = info.id };
            long min = info.value.integer.min, max = info.value.integer.max;
            for (unsigned int i = 0; i < info.count; i++)
                value.value.integer.value[i] = min + (max - min) * percent / 100;
            ok = ioctl(fd, (int)SNDRV_CTL_IOCTL_ELEM_WRITE, &value) == 0;
        }
        close(fd);
        if (ok)
            return 1;
    }
    return 0;
}

int dp_config_apply_cpu(const char *prefix, const char *profile)
{
    long limit = strcmp(profile, "eco") == 0 ? 816000 :
                 strcmp(profile, "balanced") == 0 ? 1008000 :
                 strcmp(profile, "max") == 0 ? 1416000 : 0;
    if (!limit)
        return 0;
    char policy[448], path[512];
    if (snprintf(policy, sizeof(policy), "%s/devices/system/cpu/cpufreq/policy0",
                 prefix ? prefix : "/sys") >= (int)sizeof(policy))
        return 0;
    snprintf(path, sizeof(path), "%s/scaling_available_frequencies", policy);
    FILE *f = fopen(path, "r");
    if (!f)
        return 0;
    long chosen = 0, freq;
    while (fscanf(f, "%ld", &freq) == 1) {
        if (freq <= limit && freq > chosen)
            chosen = freq;
    }
    fclose(f);
    snprintf(path, sizeof(path), "%s/scaling_min_freq", policy);
    long minimum = read_number(path);
    if (minimum <= 0 || chosen < minimum)
        return 0;
    snprintf(path, sizeof(path), "%s/scaling_max_freq", policy);
    return write_number(path, chosen) && read_number(path) == chosen;
}

int dp_config_apply(const struct dp_config *cfg, const char *sysfs_prefix,
                    const char *profile_path)
{
    int applied = 0;

    if (cfg->brightness > 0 && dp_config_apply_brightness(sysfs_prefix, cfg->brightness)) {
        applied++;
    }
    if (cfg->volume > 0 && dp_config_apply_volume(sysfs_prefix, cfg->volume))
        applied++;
    if (cfg->profile[0]) {
        if (dp_config_write_profile(profile_path, cfg->profile))
            applied++;
        dp_config_apply_cpu(sysfs_prefix, cfg->profile);
    }
    return applied;
}

int dp_config_write_profile(const char *path, const char *profile)
{
    if (!path || !*path)
        return 0;
    FILE *f = fopen(path, "w");
    if (!f)
        return 0;
    int written = fprintf(f, "%s\n", profile) > 0;
    return fclose(f) == 0 && written;
}

int dp_config_format(const struct dp_config *cfg, char *out, int outsz)
{
    return snprintf(out, (size_t)outsz, "brightness=%d volume=%d profile=%s",
                    cfg->brightness, cfg->volume,
                    cfg->profile[0] ? cfg->profile : "balanced");
}
