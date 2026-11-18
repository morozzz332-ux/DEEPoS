/* DEEPoS launcher - persistent settings in /data/config/settings.toml */
#ifndef DP_CONFIG_H
#define DP_CONFIG_H

#define DP_CONFIG_BRIGHTNESS_MAX 100
#define DP_CONFIG_VOLUME_MAX 100
#define DP_CONFIG_PROFILE_LEN 16

struct dp_config {
    int brightness;                     /* 0..100, 0 = do not touch */
    int volume;                         /* 0..100, 0 = do not touch */
    char profile[DP_CONFIG_PROFILE_LEN];/* "", "eco", "balanced", "max" */
};

/* Fills defaults: brightness 0, volume 0, profile "" (leave device alone). */
void dp_config_init(struct dp_config *cfg);

/* Loads "key = value" lines. Missing file keeps defaults, returns 0.
   Returns -1 on IO error, -2 when a value is malformed. */
int dp_config_load(struct dp_config *cfg, const char *path);

/* Writes the file atomically (tmp -> fsync -> rename). Returns 0 or -1. */
int dp_config_save(const struct dp_config *cfg, const char *path);

/* Applies "key=value". Returns 1 when applied, 0 when key is unknown,
   -2 when the value is malformed. */
int dp_config_set(struct dp_config *cfg, const char *kv);

/* Writes brightness/volume to sysfs rooted at prefix ("" = /) and the CPU
   profile to profile_path. Missing sysfs files are tolerated (fake hosts,
   devices without backlight) - returns number of applied knobs. */
int dp_config_apply(const struct dp_config *cfg, const char *sysfs_prefix,
                    const char *profile_path);

/* "brightness=40 volume=55 profile=eco" - one line, stable key order. */
int dp_config_format(const struct dp_config *cfg, char *out, int outsz);

#endif /* DP_CONFIG_H */
