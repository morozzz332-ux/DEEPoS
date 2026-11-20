/* DEEPoS power profiles - the single handler for CPU/GPU frequency limits. */
#ifndef DP_POWER_H
#define DP_POWER_H

#include <stddef.h>

struct dp_power_state {
    char cpu_min[16];
    char cpu_max[16];
    char cpu_cur[16];
    char cpu_gov[32];
    char gpu_gov[32];
    char gpu_cur[16];
};

enum dp_power_result {
    DP_POWER_APPLIED = 0,   /* limits written and verified by read-back */
    DP_POWER_UNCHANGED,     /* the device already runs at this limit */
    DP_POWER_UNSUPPORTED,   /* no cpufreq node, nothing can be applied */
    DP_POWER_ERROR,         /* the write failed or read-back differs */
};

/* Directory of the cpufreq policy that owns the CPU limits, "" when absent. */
int dp_power_locate(const char *sysfs_prefix, char *out, size_t n);
/* Reads limits and governors; returns 1 when at least the limits were read. */
int dp_power_read(const char *sysfs_prefix, struct dp_power_state *st);
/* Applies the profile and verifies the result by reading sysfs back. */
enum dp_power_result dp_power_apply(const char *sysfs_prefix, const char *profile,
                                    struct dp_power_state *before,
                                    struct dp_power_state *after,
                                    char *reason, size_t reason_n);
/* Returns the device to a previously captured state. */
enum dp_power_result dp_power_restore(const char *sysfs_prefix,
                                      const struct dp_power_state *st,
                                      char *reason, size_t reason_n);
const char *dp_power_result_name(enum dp_power_result result);
/* "profile=balanced cpu=408000..1008000 governor=performance gpu=simple_ondemand" */
int dp_power_format(const char *profile, const struct dp_power_state *st,
                    char *out, size_t n);
/* Snapshot taken before a game session and restored after it. */
int dp_power_snapshot_save(const char *path, const struct dp_power_state *st);
int dp_power_snapshot_load(const char *path, struct dp_power_state *st);

#endif
