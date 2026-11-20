/* DEEPoS power profiles: one place that writes CPU/GPU limits and confirms them. */
#include "dp_power.h"

#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define GPU_PATH "/class/devfreq/ff400000.gpu"
#define POLICY_REL "devices/system/cpu/cpufreq/policy0"

static void note(char *out, size_t n, const char *fmt, ...)
{
    va_list ap;
    if (!out || n == 0)
        return;
    va_start(ap, fmt);
    vsnprintf(out, n, fmt, ap);
    va_end(ap);
}

static void trim(char *s)
{
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r' ||
                     s[n - 1] == ' ' || s[n - 1] == '\t'))
        s[--n] = 0;
}

static int read_text(const char *path, char *out, size_t n)
{
    FILE *f = fopen(path, "r");
    if (!f)
        return 0;
    int ok = fgets(out, (int)n, f) != NULL;
    fclose(f);
    if (!ok)
        return 0;
    trim(out);
    return out[0] != 0;
}

static long read_number(const char *path)
{
    char buf[32];
    char *end = NULL;
    if (!read_text(path, buf, sizeof(buf)))
        return -1;
    long value = strtol(buf, &end, 10);
    return end != buf ? value : -1;
}

static int write_text(const char *path, const char *value)
{
    FILE *f = fopen(path, "w");
    int ok;
    if (!f)
        return 0;
    ok = fprintf(f, "%s\n", value) > 0;
    if (fclose(f) != 0)
        ok = 0;
    return ok;
}

static int write_number(const char *path, long value)
{
    char buf[32];
    snprintf(buf, sizeof(buf), "%ld", value);
    return write_text(path, buf);
}

static int join(char *out, size_t n, const char *dir, const char *name)
{
    int len = snprintf(out, n, "%s/%s", dir, name);
    return len > 0 && (size_t)len < n;
}

int dp_power_locate(const char *sysfs_prefix, char *out, size_t n)
{
    static const char *rels[] = {
        "", POLICY_REL, "devices/system/cpu/cpufreq/cpu0",
        "cpufreq", "policy0",
    };
    const char *root = (sysfs_prefix && sysfs_prefix[0]) ? sysfs_prefix : "/sys";
    char dir[512], probe[640];

    for (size_t i = 0; i < sizeof(rels) / sizeof(rels[0]); i++) {
        if (rels[i][0]) {
            if (!join(dir, sizeof(dir), root, rels[i]))
                continue;
        } else {
            snprintf(dir, sizeof(dir), "%s", root);
        }
        if (join(probe, sizeof(probe), dir, "scaling_available_frequencies") &&
            access(probe, R_OK) == 0) {
            snprintf(out, n, "%s", dir);
            return 1;
        }
    }
    return 0;
}

int dp_power_read(const char *sysfs_prefix, struct dp_power_state *st)
{
    const char *root = (sysfs_prefix && sysfs_prefix[0]) ? sysfs_prefix : "/sys";
    char dir[512], path[640];
    int found;

    memset(st, 0, sizeof(*st));
    found = dp_power_locate(root, dir, sizeof(dir));
    if (found) {
        if (join(path, sizeof(path), dir, "scaling_min_freq"))
            read_text(path, st->cpu_min, sizeof(st->cpu_min));
        if (join(path, sizeof(path), dir, "scaling_max_freq"))
            read_text(path, st->cpu_max, sizeof(st->cpu_max));
        if (join(path, sizeof(path), dir, "scaling_cur_freq"))
            read_text(path, st->cpu_cur, sizeof(st->cpu_cur));
        if (join(path, sizeof(path), dir, "scaling_governor"))
            read_text(path, st->cpu_gov, sizeof(st->cpu_gov));
    }
    if (join(path, sizeof(path), root, GPU_PATH "/governor"))
        read_text(path, st->gpu_gov, sizeof(st->gpu_gov));
    if (join(path, sizeof(path), root, GPU_PATH "/cur_freq"))
        read_text(path, st->gpu_cur, sizeof(st->gpu_cur));
    return found;
}

static long profile_limit(const char *profile)
{
    if (!strcmp(profile, "eco"))
        return 816000;
    if (!strcmp(profile, "balanced"))
        return 1008000;
    if (!strcmp(profile, "max"))
        return 1296000;
    return 0;
}

/* The measured board has no 1296 MHz OPP: a "max" request must still reach the
 * highest OPP it can, but never above the 1416 MHz search ceiling. */
#define DP_POWER_CEILING 1416000L

enum dp_power_result dp_power_apply(const char *sysfs_prefix, const char *profile,
                                    struct dp_power_state *before,
                                    struct dp_power_state *after,
                                    char *reason, size_t reason_n)
{
    const char *root = (sysfs_prefix && sysfs_prefix[0]) ? sysfs_prefix : "/sys";
    struct dp_power_state current;
    char dir[512], avail[640], minp[640], maxp[640];
    long limit = profile_limit(profile);
    long chosen = 0, fallback = 0, minimum, maximum, freq;
    int lowered = 0;

    if (reason && reason_n)
        reason[0] = 0;
    dp_power_read(root, &current);
    if (before)
        *before = current;
    if (after)
        *after = current;
    if (limit <= 0) {
        note(reason, reason_n, "неизвестный профиль %s", profile ? profile : "");
        return DP_POWER_ERROR;
    }
    if (!dp_power_locate(root, dir, sizeof(dir))) {
        note(reason, reason_n, "нет cpufreq в %s", root);
        return DP_POWER_UNSUPPORTED;
    }
    if (!join(avail, sizeof(avail), dir, "scaling_available_frequencies") ||
        !join(minp, sizeof(minp), dir, "scaling_min_freq") ||
        !join(maxp, sizeof(maxp), dir, "scaling_max_freq")) {
        note(reason, reason_n, "путь policy0 слишком длинный");
        return DP_POWER_ERROR;
    }
    FILE *f = fopen(avail, "r");
    if (f) {
        while (fscanf(f, "%ld", &freq) == 1) {
            if (freq <= limit && freq > chosen)
                chosen = freq;
            /* Lowest OPP above the target, still within the ceiling. */
            if (!strcmp(profile, "max") && freq > limit && freq <= DP_POWER_CEILING &&
                (fallback == 0 || freq < fallback))
                fallback = freq;
        }
        fclose(f);
    }
    if (chosen <= 0) {
        note(reason, reason_n, "нет частоты не выше %ld", limit);
        return DP_POWER_UNSUPPORTED;
    }
    /* 1296 MHz is absent on the measured board: take the next OPP up. */
    if (!strcmp(profile, "max") && chosen < limit && fallback > 0)
        chosen = fallback;
    minimum = read_number(minp);
    maximum = read_number(maxp);
    if (minimum < 0 || maximum < 0) {
        note(reason, reason_n, "не читаются пределы policy0");
        return DP_POWER_ERROR;
    }
    if (chosen == maximum && minimum <= chosen) {
        note(reason, reason_n, "уже %ld", chosen);
        return DP_POWER_UNCHANGED;
    }
    if (chosen < minimum) {
        /* The floor may not sit above the ceiling: lower it first. */
        if (!write_number(minp, chosen) || read_number(minp) != chosen) {
            note(reason, reason_n, "min %ld выше цели %ld", minimum, chosen);
            return DP_POWER_ERROR;
        }
        lowered = 1;
    }
    if (!write_number(maxp, chosen) || read_number(maxp) != chosen) {
        note(reason, reason_n, "не удалось записать max %ld", chosen);
        return DP_POWER_ERROR;
    }
    dp_power_read(root, &current);
    if (after)
        *after = current;
    if (lowered)
        note(reason, reason_n, "max %ld, min снижен с %ld", chosen, minimum);
    else
        note(reason, reason_n, "max %ld", chosen);
    return DP_POWER_APPLIED;
}

enum dp_power_result dp_power_restore(const char *sysfs_prefix,
                                      const struct dp_power_state *st,
                                      char *reason, size_t reason_n)
{
    const char *root = (sysfs_prefix && sysfs_prefix[0]) ? sysfs_prefix : "/sys";
    char dir[512], minp[640], maxp[640], govp[640], path[640];
    long want_min = st->cpu_min[0] ? strtol(st->cpu_min, NULL, 10) : -1;
    long want_max = st->cpu_max[0] ? strtol(st->cpu_max, NULL, 10) : -1;
    long cur_min, cur_max;

    if (reason && reason_n)
        reason[0] = 0;
    if (want_min <= 0 && want_max <= 0) {
        note(reason, reason_n, "нет снимка питания");
        return DP_POWER_UNSUPPORTED;
    }
    if (want_min > 0 && want_max > 0 && want_min > want_max)
        want_min = want_max;
    if (!dp_power_locate(root, dir, sizeof(dir))) {
        note(reason, reason_n, "нет cpufreq в %s", root);
        return DP_POWER_UNSUPPORTED;
    }
    if (!join(minp, sizeof(minp), dir, "scaling_min_freq") ||
        !join(maxp, sizeof(maxp), dir, "scaling_max_freq") ||
        !join(govp, sizeof(govp), dir, "scaling_governor")) {
        note(reason, reason_n, "путь policy0 слишком длинный");
        return DP_POWER_ERROR;
    }
    cur_min = read_number(minp);
    cur_max = read_number(maxp);
    if (want_max > 0 && want_max < cur_min && want_min > 0) {
        if (!write_number(minp, want_min) || read_number(minp) != want_min) {
            note(reason, reason_n, "не удалось вернуть min %ld", want_min);
            return DP_POWER_ERROR;
        }
    }
    if (want_max > 0 && cur_max != want_max) {
        if (!write_number(maxp, want_max) || read_number(maxp) != want_max) {
            note(reason, reason_n, "не удалось вернуть max %ld", want_max);
            return DP_POWER_ERROR;
        }
    }
    if (want_min > 0 && read_number(minp) != want_min) {
        if (!write_number(minp, want_min) || read_number(minp) != want_min) {
            note(reason, reason_n, "не удалось вернуть min %ld", want_min);
            return DP_POWER_ERROR;
        }
    }
    if (st->cpu_gov[0])
        write_text(govp, st->cpu_gov);
    if (st->gpu_gov[0] && join(path, sizeof(path), root, GPU_PATH "/governor"))
        write_text(path, st->gpu_gov);
    if (want_max > 0 && read_number(maxp) != want_max) {
        note(reason, reason_n, "max не вернулся к %ld", want_max);
        return DP_POWER_ERROR;
    }
    note(reason, reason_n, "max %ld governor %s", want_max,
         st->cpu_gov[0] ? st->cpu_gov : "-");
    return DP_POWER_APPLIED;
}

const char *dp_power_result_name(enum dp_power_result result)
{
    switch (result) {
    case DP_POWER_APPLIED:
        return "applied";
    case DP_POWER_UNCHANGED:
        return "unchanged";
    case DP_POWER_UNSUPPORTED:
        return "unsupported";
    default:
        return "error";
    }
}

int dp_power_format(const char *profile, const struct dp_power_state *st,
                    char *out, size_t n)
{
    return snprintf(out, n, "profile=%s cpu=%s..%s governor=%s gpu=%s",
                    profile && profile[0] ? profile : "-",
                    st->cpu_min[0] ? st->cpu_min : "-",
                    st->cpu_max[0] ? st->cpu_max : "-",
                    st->cpu_gov[0] ? st->cpu_gov : "-",
                    st->gpu_gov[0] ? st->gpu_gov : "-");
}

static const char *field_or_dash(const char *value)
{
    return value[0] ? value : "-";
}

int dp_power_snapshot_save(const char *path, const struct dp_power_state *st)
{
    char tmp[600];
    FILE *f;
    int ok;

    if (!path || !*path)
        return 0;
    if (snprintf(tmp, sizeof(tmp), "%s.tmp", path) >= (int)sizeof(tmp))
        return 0;
    f = fopen(tmp, "w");
    if (!f)
        return 0;
    ok = fprintf(f, "%s\t%s\t%s\t%s\t%s\n",
                 field_or_dash(st->cpu_min), field_or_dash(st->cpu_max),
                 field_or_dash(st->cpu_gov), field_or_dash(st->gpu_gov),
                 field_or_dash(st->gpu_cur)) > 0;
    if (fflush(f) != 0 || fclose(f) != 0)
        ok = 0;
    if (!ok || rename(tmp, path) != 0) {
        unlink(tmp);
        return 0;
    }
    return 1;
}

static void copy_field(char *dst, size_t n, const char *src)
{
    if (!src || !src[0] || (src[0] == '-' && src[1] == 0)) {
        dst[0] = 0;
        return;
    }
    snprintf(dst, n, "%s", src);
}

int dp_power_snapshot_load(const char *path, struct dp_power_state *st)
{
    char line[256], *fields[5], *p;
    int count = 0;
    FILE *f;

    if (!path || !*path)
        return 0;
    f = fopen(path, "r");
    if (!f)
        return 0;
    if (!fgets(line, sizeof(line), f)) {
        fclose(f);
        return 0;
    }
    fclose(f);
    trim(line);
    p = line;
    while (count < 5) {
        fields[count++] = p;
        p = strchr(p, '\t');
        if (!p)
            break;
        *p++ = 0;
    }
    memset(st, 0, sizeof(*st));
    if (count > 0)
        copy_field(st->cpu_min, sizeof(st->cpu_min), fields[0]);
    if (count > 1)
        copy_field(st->cpu_max, sizeof(st->cpu_max), fields[1]);
    if (count > 2)
        copy_field(st->cpu_gov, sizeof(st->cpu_gov), fields[2]);
    if (count > 3)
        copy_field(st->gpu_gov, sizeof(st->gpu_gov), fields[3]);
    if (count > 4)
        copy_field(st->gpu_cur, sizeof(st->gpu_cur), fields[4]);
    return st->cpu_max[0] != 0;
}
