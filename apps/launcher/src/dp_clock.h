#ifndef DP_CLOCK_H
#define DP_CLOCK_H

#include <time.h>

struct dp_clock_settings {
    int zone;
    time_t anchor;
};

enum { DP_CLOCK_DAY, DP_CLOCK_MONTH, DP_CLOCK_YEAR, DP_CLOCK_HOUR, DP_CLOCK_MINUTE,
       DP_CLOCK_FIELDS };

int dp_clock_zone_count(void);
const char *dp_clock_zone_label(int zone);
int dp_clock_select_zone(int zone, int system_wide);
void dp_clock_load(const char *data, struct dp_clock_settings *clock);
int dp_clock_save(const char *data, const struct dp_clock_settings *clock);
int dp_clock_set(time_t utc);
void dp_clock_edit(struct tm *draft, int field, int direction);
time_t dp_clock_to_epoch(struct tm draft);

#endif
