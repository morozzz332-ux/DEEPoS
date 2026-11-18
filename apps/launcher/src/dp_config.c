/* DEEPoS launcher - persistent settings, applied without a compositor. */
#define _POSIX_C_SOURCE 200809L

#include "dp_config.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DP_CFG_LINE 256

void dp_config_init(struct dp_config *cfg)
{
    cfg->brightness = 0;
    cfg->volume = 0;
    cfg->profile[0] = '\0';
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
    if (snprintf(tmp, sizeof(tmp), "%s.tmp", path) >= (int)sizeof(tmp)) {
        return -1;
    }
    FILE *f = fopen(tmp, "w");
    if (!f) {
        return -1;
    }
    fprintf(f, "# DEEPoS settings\n");
    fprintf(f, "brightness = %d\n", cfg->brightness);
    fprintf(f, "volume = %d\n", cfg->volume);
    fprintf(f, "profile = %s\n", cfg->profile[0] ? cfg->profile : "balanced");
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

static int write_value(const char *dir, const char *file, int value)
{
    char path[512];
    if (snprintf(path, sizeof(path), "%s%s", dir, file) >= (int)sizeof(path)) {
        return 0;
    }
    FILE *f = fopen(path, "w");
    if (!f) {
        return 0;
    }
    int ok = fprintf(f, "%d\n", value) > 0;
    fclose(f);
    return ok ? 1 : 0;
}

static int write_first_backlight(const char *prefix, int percent)
{
    char path[512];
    const char *names[] = {"/backlight/deepos-bl/brightness", "/backlight/backlight/brightness",
                           "/backlight/pwm-backlight/brightness"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
        if (snprintf(path, sizeof(path), "%s%s", prefix, names[i]) >= (int)sizeof(path)) {
            continue;
        }
        FILE *f = fopen(path, "w");
        if (!f) {
            continue;
        }
        /* Sysfs backlight takes raw steps; 0..100 percent maps to 1..45 here
           because the panel is driven by pwm-backlight with 46 levels. */
        int raw = (percent * 45) / 100;
        if (raw < 1) {
            raw = 1;
        }
        int ok = fprintf(f, "%d\n", raw) > 0;
        fclose(f);
        if (ok) {
            return 1;
        }
    }
    return 0;
}

int dp_config_apply(const struct dp_config *cfg, const char *sysfs_prefix,
                    const char *profile_path)
{
    const char *prefix = sysfs_prefix ? sysfs_prefix : "";
    int applied = 0;

    if (cfg->brightness > 0 && write_first_backlight(prefix, cfg->brightness)) {
        applied++;
    }
    if (cfg->volume > 0) {
        if (write_value(prefix, "/class/sound/card0/controlC0/volume_percent", cfg->volume) ||
            write_value(prefix, "/devices/platform/ff400000.i2s/sound/card0/volume_percent",
                        cfg->volume)) {
            applied++;
        }
    }
    if (cfg->profile[0] && profile_path && profile_path[0]) {
        FILE *f = fopen(profile_path, "w");
        if (f) {
            fprintf(f, "%s\n", cfg->profile);
            fclose(f);
            applied++;
        }
    }
    return applied;
}

int dp_config_format(const struct dp_config *cfg, char *out, int outsz)
{
    return snprintf(out, (size_t)outsz, "brightness=%d volume=%d profile=%s",
                    cfg->brightness, cfg->volume,
                    cfg->profile[0] ? cfg->profile : "balanced");
}
