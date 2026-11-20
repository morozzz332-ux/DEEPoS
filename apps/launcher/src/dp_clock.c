#include "dp_clock.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const struct zone {
    const char *id;
    const char *label;
} zones[] = {
#define ZONE(id, label) {id, label},
#include "dp_zones.def"
#undef ZONE
};

int dp_clock_zone_count(void)
{
    return (int)(sizeof(zones) / sizeof(zones[0]));
}

const char *dp_clock_zone_label(int zone)
{
    return zones[zone].label;
}

int dp_clock_select_zone(int zone, int system_wide)
{
    char tz[100];
    snprintf(tz, sizeof(tz), ":/usr/share/zoneinfo/%s", zones[zone].id);
    if (access(tz + 1, R_OK) != 0)
        return -1;
    if (system_wide) {
        const char *next = "/run/deepos-localtime.new";
        unlink(next);
        if (symlink(tz + 1, next) != 0)
            return -1;
        if (rename(next, "/run/deepos-localtime") != 0) {
            unlink(next);
            return -1;
        }
    }
    if (setenv("TZ", tz, 1) != 0)
        return -1;
    tzset();
    return 0;
}

void dp_clock_load(const char *data, struct dp_clock_settings *clock)
{
    char path[512], zone[64];
    long long anchor = 0;
    *clock = (struct dp_clock_settings){0};
    snprintf(path, sizeof(path), "%s/config/clock", data);
    FILE *file = fopen(path, "r");
    if (!file)
        return;
    int fields = fscanf(file, "%63s %lld", zone, &anchor);
    fclose(file);
    if (fields != 2)
        return;
    for (int i = 0; i < dp_clock_zone_count(); i++)
        if (!strcmp(zones[i].id, zone)) {
            clock->zone = i;
            break;
        }
    if (anchor >= 946598400LL && anchor < 4102531200LL)
        clock->anchor = (time_t)anchor;
}

int dp_clock_save(const char *data, const struct dp_clock_settings *clock)
{
    char path[512], temporary[528];
    if (snprintf(path, sizeof(path), "%s/config/clock", data) >= (int)sizeof(path))
        return -1;
    snprintf(temporary, sizeof(temporary), "%s.XXXXXX", path);
    int fd = mkstemp(temporary);
    if (fd < 0)
        return -1;
    int ok = dprintf(fd, "%s %lld\n", zones[clock->zone].id, (long long)clock->anchor) > 0 &&
             fsync(fd) == 0;
    if (close(fd) != 0)
        ok = 0;
    if (!ok || rename(temporary, path) != 0) {
        unlink(temporary);
        return -1;
    }
    return 0;
}

int dp_clock_set(time_t utc)
{
    struct timespec ts = { .tv_sec = utc };
    return clock_settime(CLOCK_REALTIME, &ts);
}

static int days_in_month(int year, int month)
{
    const int days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return days[month] + (month == 1 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
}

static int step(int value, int first, int last, int direction)
{
    value += direction;
    return value < first ? last : value > last ? first : value;
}

void dp_clock_edit(struct tm *draft, int field, int direction)
{
    switch (field) {
    case DP_CLOCK_DAY:
        draft->tm_mday = step(draft->tm_mday, 1,
                              days_in_month(draft->tm_year + 1900, draft->tm_mon), direction);
        break;
    case DP_CLOCK_MONTH: draft->tm_mon = step(draft->tm_mon, 0, 11, direction); break;
    case DP_CLOCK_YEAR: draft->tm_year = step(draft->tm_year, 100, 199, direction); break;
    case DP_CLOCK_HOUR: draft->tm_hour = step(draft->tm_hour, 0, 23, direction); break;
    case DP_CLOCK_MINUTE: draft->tm_min = step(draft->tm_min, 0, 59, direction); break;
    }
    int max_days = days_in_month(draft->tm_year + 1900, draft->tm_mon);
    if (draft->tm_mday > max_days)
        draft->tm_mday = max_days;
}

time_t dp_clock_to_epoch(struct tm draft)
{
    struct tm target = draft;
    draft.tm_sec = 0;
    draft.tm_isdst = -1;
    time_t result = mktime(&draft);
    if (draft.tm_year != target.tm_year || draft.tm_mon != target.tm_mon ||
        draft.tm_mday != target.tm_mday || draft.tm_hour != target.tm_hour ||
        draft.tm_min != target.tm_min)
        return (time_t)-1;
    return result;
}
