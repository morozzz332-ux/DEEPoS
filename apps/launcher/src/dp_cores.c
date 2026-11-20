#include "dp_cores.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int id_valid(const char *id)
{
    const char *allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
    size_t len = strlen(id);
    return len > 0 && len < DP_CORE_NAME && strspn(id, allowed) == len;
}

static FILE *open_catalog(const char *data)
{
    char path[512];
    snprintf(path, sizeof(path), "%s/emus/cores.tsv", data);
    FILE *file = fopen(path, "r");
    return file ? file : fopen(DP_CORE_ASSETS "/cores.tsv", "r");
}

int dp_core_list(struct dp_cores *list, const char *data, const char *system)
{
    list->count = 0;
    FILE *file = open_catalog(data);
    if (!file)
        return 0;
    char line[DP_CORE_MAX * DP_CORE_NAME];
    while (fgets(line, sizeof(line), file)) {
        char *values = strchr(line, '\t');
        if (!values)
            continue;
        *values++ = '\0';
        if (strcmp(line, system))
            continue;
        char *save = NULL;
        for (char *name = strtok_r(values, " \r\n", &save);
             name && list->count < DP_CORE_MAX;
             name = strtok_r(NULL, " \r\n", &save)) {
            if (!id_valid(name))
                continue;
            char path[600];
            snprintf(path, sizeof(path), "%s/emus/cores/%s_libretro.so", data, name);
            if (access(path, R_OK) != 0) {
                snprintf(path, sizeof(path), DP_CORE_ASSETS "/cores/%s_libretro.so", name);
                if (access(path, R_OK) != 0)
                    continue;
            }
            snprintf(list->names[list->count++], DP_CORE_NAME, "%s", name);
        }
        break;
    }
    fclose(file);
    return list->count;
}

static int core_path(char *path, size_t size, const char *data, const char *system)
{
    if (!id_valid(system))
        return 0;
    int n = snprintf(path, size, "%s/config/core-%s", data, system);
    return n >= 0 && (size_t)n < size;
}

int dp_core_read(const char *data, const char *system, char *name, size_t size)
{
    char path[512], line[DP_CORE_NAME];
    if (!core_path(path, sizeof(path), data, system))
        return 0;
    FILE *file = fopen(path, "r");
    if (!file)
        return 0;
    int valid = fscanf(file, "%63s", line) == 1 && id_valid(line);
    fclose(file);
    if (valid)
        snprintf(name, size, "%s", line);
    return valid;
}

int dp_core_save(const char *data, const char *system, const char *name)
{
    char path[512], temporary[528];
    if (!core_path(path, sizeof(path), data, system))
        return -1;
    if (!name)
        return unlink(path) == 0 || errno == ENOENT ? 0 : -1;
    if (!id_valid(name))
        return -1;
    snprintf(temporary, sizeof(temporary), "%s.XXXXXX", path);
    int fd = mkstemp(temporary);
    if (fd < 0)
        return -1;
    int ok = dprintf(fd, "%s\n", name) > 0 && fsync(fd) == 0;
    if (close(fd) != 0)
        ok = 0;
    if (!ok || rename(temporary, path) != 0) {
        unlink(temporary);
        return -1;
    }
    return 0;
}

int dp_core_default_command(const char *command)
{
    const char *prefix = "/usr/local/bin/retroarch-game.sh ";
    size_t len = strlen(prefix);
    if (strncmp(command, prefix, len))
        return 0;
    const char *space = strchr(command + len, ' ');
    if (!space || strcmp(space, " %ROM%") != 0 || space - (command + len) >= DP_CORE_NAME)
        return 0;
    char name[DP_CORE_NAME];
    snprintf(name, sizeof(name), "%.*s", (int)(space - (command + len)), command + len);
    return id_valid(name);
}
