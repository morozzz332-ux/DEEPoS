#ifndef DP_CORES_H
#define DP_CORES_H

#include <stddef.h>

#define DP_CORE_MAX 24
#define DP_CORE_NAME 64
#define DP_CORE_ASSETS "/usr/share/deepos/extra-emulators"

struct dp_cores {
    int count;
    char names[DP_CORE_MAX][DP_CORE_NAME];
};

int dp_core_list(struct dp_cores *list, const char *data, const char *system);
int dp_core_read(const char *data, const char *system, char *name, size_t size);
int dp_core_save(const char *data, const char *system, const char *name);
int dp_core_default_command(const char *command);

#endif
