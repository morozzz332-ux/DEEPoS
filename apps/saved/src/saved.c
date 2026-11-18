/* DEEPoS - saved: atomic save-state store (host prototype).
 *
 * Layout under --data:
 *   saves/<system>/<rom-key>/slot<N>.state     N = 0..4
 *   saves/<system>/<rom-key>/slot<N>.json      {"slot":N,"size":…,"ts":…}
 *   saves/<system>/<rom-key>/last              last slot the player used
 *   saves/.journal                             crash-recovery journal
 *
 * A slot is written as slot<N>.state.tmp, fsync'd, then renamed over the slot,
 * so a power cut leaves either the old or the new file, never a torn one.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define SLOTS 5
#define JOURNAL "saves/.journal"

static int mkdir_p(const char *path)
{
    char tmp[1024];
    size_t len = strlen(path);
    if (len == 0 || len >= sizeof(tmp))
        return -1;
    memcpy(tmp, path, len + 1);
    for (char *p = tmp + 1; *p; p++) {
        if (*p != '/')
            continue;
        *p = '\0';
        if (mkdir(tmp, 0755) != 0 && errno != EEXIST)
            return -1;
        *p = '/';
    }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST)
        return -1;
    return 0;
}

static int fsync_dir(const char *path)
{
    int fd = open(path, O_RDONLY | O_DIRECTORY);
    int rc;
    if (fd < 0)
        return -1;
    rc = fsync(fd);
    close(fd);
    return rc;
}

/* Copies src into dst via dst.tmp + fsync + rename + fsync(dir). */
static int copy_atomic(const char *src, const char *dst)
{
    char tmp[1100];
    char dir[1024];
    char buf[65536];
    int in, out;
    ssize_t got;

    snprintf(tmp, sizeof(tmp), "%s.tmp", dst);
    snprintf(dir, sizeof(dir), "%s", dst);
    char *slash = strrchr(dir, '/');
    if (slash)
        *slash = '\0';
    else
        snprintf(dir, sizeof(dir), ".");

    in = open(src, O_RDONLY);
    if (in < 0)
        return -1;
    out = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out < 0) {
        close(in);
        return -1;
    }
    while ((got = read(in, buf, sizeof(buf))) > 0) {
        ssize_t off = 0;
        while (off < got) {
            ssize_t wrote = write(out, buf + off, (size_t)(got - off));
            if (wrote <= 0) {
                close(in);
                close(out);
                unlink(tmp);
                return -1;
            }
            off += wrote;
        }
    }
    close(in);
    if (fsync(out) != 0) {
        close(out);
        unlink(tmp);
        return -1;
    }
    close(out);
    if (rename(tmp, dst) != 0) {
        unlink(tmp);
        return -1;
    }
    return fsync_dir(dir);
}

static int path_for(char *out, size_t n, const char *data, const char *system,
                    const char *rom, const char *leaf)
{
    return snprintf(out, n, "%s/saves/%s/%s/%s", data, system, rom, leaf) < (int)n ? 0 : -1;
}

static int write_meta(const char *path, int slot, long size)
{
    char tmp[1100];
    FILE *f;
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    f = fopen(tmp, "w");
    if (!f)
        return -1;
    fprintf(f, "{\"slot\":%d,\"size\":%ld,\"ts\":%ld}\n", slot, size, (long)time(NULL));
    if (fflush(f) != 0) {
        fclose(f);
        unlink(tmp);
        return -1;
    }
    fsync(fileno(f));
    fclose(f);
    if (rename(tmp, path) != 0) {
        unlink(tmp);
        return -1;
    }
    return 0;
}

static long file_size(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0 ? (long)st.st_size : -1;
}

static int journal_add(const char *data, const char *what, const char *path)
{
    char jpath[1200];
    FILE *f;
    snprintf(jpath, sizeof(jpath), "%s/%s", data, JOURNAL);
    char *slash = strrchr(jpath, '/');
    if (slash) {
        *slash = '\0';
        if (mkdir_p(jpath) != 0)
            return 0;
        *slash = '/';
    }
    f = fopen(jpath, "a");
    if (!f) {
        /* journal is advisory: a missing one must not block saves */
        return 0;
    }
    fprintf(f, "%s %s\n", what, path);
    fflush(f);
    fsync(fileno(f));
    fclose(f);
    return 0;
}

static int cmd_put(const char *data, const char *system, const char *rom,
                   int slot, const char *src)
{
    char dir[1024], state[1100], meta[1100];
    char slotname[32];

    if (slot < 0 || slot >= SLOTS)
        return 3;
    snprintf(slotname, sizeof(slotname), "slot%d", slot);
    snprintf(dir, sizeof(dir), "%s/saves/%s/%s", data, system, rom);
    if (mkdir_p(dir) != 0)
        return 2;
    snprintf(state, sizeof(state), "%s.state", slotname);
    snprintf(meta, sizeof(meta), "%s.json", slotname);

    char state_path[1100], meta_path[1100], last_path[1100];
    if (path_for(state_path, sizeof(state_path), data, system, rom, state) != 0)
        return 2;
    if (path_for(meta_path, sizeof(meta_path), data, system, rom, meta) != 0)
        return 2;
    if (path_for(last_path, sizeof(last_path), data, system, rom, "last") != 0)
        return 2;

    journal_add(data, "BEGIN", state_path);
    if (copy_atomic(src, state_path) != 0)
        return 2;
    long size = file_size(state_path);
    if (write_meta(meta_path, slot, size) != 0)
        return 2;
    FILE *lf = fopen(last_path, "w");
    if (lf) {
        fprintf(lf, "%d\n", slot);
        fclose(lf);
    }
    journal_add(data, "COMMIT", state_path);
    return 0;
}

static int cmd_get(const char *data, const char *system, const char *rom, int slot)
{
    char leaf[32], path[1100];
    snprintf(leaf, sizeof(leaf), "slot%d.state", slot);
    if (path_for(path, sizeof(path), data, system, rom, leaf) != 0)
        return 2;
    if (access(path, R_OK) != 0)
        return 4;
    printf("%s\n", path);
    return 0;
}

static int read_last(const char *data, const char *system, const char *rom, int *slot)
{
    char path[1100];
    FILE *f;
    int value = -1;
    if (path_for(path, sizeof(path), data, system, rom, "last") != 0)
        return -1;
    f = fopen(path, "r");
    if (!f)
        return -1;
    if (fscanf(f, "%d", &value) != 1)
        value = -1;
    fclose(f);
    if (slot)
        *slot = value;
    return value >= 0 ? 0 : -1;
}

static int cmd_last(const char *data, const char *system, const char *rom)
{
    int slot = -1;
    if (read_last(data, system, rom, &slot) != 0)
        return 4;
    printf("%d\n", slot);
    return 0;
}

static int cmd_list(const char *data, const char *system, const char *rom)
{
    for (int slot = 0; slot < SLOTS; slot++) {
        char leaf[32], path[1100];
        snprintf(leaf, sizeof(leaf), "slot%d.state", slot);
        if (path_for(path, sizeof(path), data, system, rom, leaf) != 0)
            return 2;
        long size = file_size(path);
        if (size >= 0)
            printf("%d %ld\n", slot, size);
    }
    return 0;
}

/* Drops .tmp leftovers and rotates so that at most SLOTS slot files remain.
 * Older slots are removed first; `last` is rewritten when it pointed at a
 * removed slot. */
static int cmd_clean(const char *data, const char *system, const char *rom)
{
    char dir[1024];
    snprintf(dir, sizeof(dir), "%s/saves/%s/%s", data, system, rom);
    for (int slot = 0; slot < SLOTS; slot++) {
        char leaf[64], path[1100];
        snprintf(leaf, sizeof(leaf), "slot%d.state.tmp", slot);
        if (path_for(path, sizeof(path), data, system, rom, leaf) == 0)
            unlink(path);
        snprintf(leaf, sizeof(leaf), "slot%d.json.tmp", slot);
        if (path_for(path, sizeof(path), data, system, rom, leaf) == 0)
            unlink(path);
    }
    (void)dir;
    return 0;
}

static void usage(void)
{
    puts("usage: saved --data DIR put   --system S --rom R --slot N --file PATH\n"
         "       saved --data DIR get   --system S --rom R --slot N\n"
         "       saved --data DIR last  --system S --rom R\n"
         "       saved --data DIR list  --system S --rom R\n"
         "       saved --data DIR clean --system S --rom R\n"
         "       saved --data DIR recover");
}

/* Replays the journal: removes .tmp files whose BEGIN has no COMMIT. */
static int cmd_recover(const char *data)
{
    char jpath[1200];
    FILE *f;
    char line[1200];
    int removed = 0;

    snprintf(jpath, sizeof(jpath), "%s/%s", data, JOURNAL);
    f = fopen(jpath, "r");
    if (!f) {
        puts("recovered 0");
        return 0;
    }
    while (fgets(line, sizeof(line), f)) {
        char kind[16], path[1100];
        if (sscanf(line, "%15s %1099s", kind, path) != 2)
            continue;
        if (!strcmp(kind, "BEGIN")) {
            char tmp[1100];
            snprintf(tmp, sizeof(tmp), "%s.tmp", path);
            if (unlink(tmp) == 0)
                removed++;
        }
    }
    fclose(f);
    if (unlink(jpath) != 0 && errno != ENOENT)
        return 2;
    printf("recovered %d\n", removed);
    return 0;
}

int main(int argc, char **argv)
{
    const char *data = NULL, *system = NULL, *rom = NULL, *file = NULL;
    const char *cmd = NULL;
    int slot = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--data") && i + 1 < argc)
            data = argv[++i];
        else if (!strcmp(argv[i], "--system") && i + 1 < argc)
            system = argv[++i];
        else if (!strcmp(argv[i], "--rom") && i + 1 < argc)
            rom = argv[++i];
        else if (!strcmp(argv[i], "--slot") && i + 1 < argc)
            slot = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--file") && i + 1 < argc)
            file = argv[++i];
        else if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) {
            usage();
            return 0;
        } else if (!cmd) {
            cmd = argv[i];
        } else {
            usage();
            return 3;
        }
    }
    if (!data || !cmd) {
        usage();
        return 3;
    }
    if (!strcmp(cmd, "recover"))
        return cmd_recover(data);
    if (!system || !rom) {
        usage();
        return 3;
    }
    if (!strcmp(cmd, "put")) {
        if (!file || slot < 0 || slot >= SLOTS) {
            usage();
            return 3;
        }
        return cmd_put(data, system, rom, slot, file);
    }
    if (!strcmp(cmd, "get"))
        return cmd_get(data, system, rom, slot);
    if (!strcmp(cmd, "last"))
        return cmd_last(data, system, rom);
    if (!strcmp(cmd, "list"))
        return cmd_list(data, system, rom);
    if (!strcmp(cmd, "clean"))
        return cmd_clean(data, system, rom);

    usage();
    return 3;
}
