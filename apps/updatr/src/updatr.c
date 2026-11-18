/*
 * updatr - DEEPoS A/B boot bookkeeping and slot installer.
 *
 * The root filesystem lives in two squashfs slots (SYS_A / SYS_B on the card).
 * A small JSON file on the DATA partition records which slot to boot next, how
 * many boot attempts the current slot already consumed and whether the last
 * update must be rolled back. This tool mirrors tools/update.py so the device
 * needs no Python, and adds "install" which copies a rootfs image into the
 * inactive slot.
 *
 * Usage:
 *   updatr --state DIR status
 *   updatr --state DIR decide
 *   updatr --state DIR begin   [--max-attempts N]
 *   updatr --state DIR good
 *   updatr --state DIR switch A|B
 *   updatr --state DIR install --slot A|B --file IMG --dev TARGET
 *
 * Exit codes: 0 ok, 2 io error, 3 bad arguments/state, 4 target too small.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define STATE_NAME "boot.json"
#define MAX_ATTEMPTS 3

struct state {
    char slot[2];
    int attempts;
    int rollback;
    int generation;
};

static void state_default(struct state *st)
{
    st->slot[0] = 'A';
    st->slot[1] = '\0';
    st->attempts = 0;
    st->rollback = 0;
    st->generation = 0;
}

static int ensure_dir(const char *dir)
{
    if (mkdir(dir, 0755) == 0 || errno == EEXIST)
        return 0;
    fprintf(stderr, "updatr: cannot create %s: %s\n", dir, strerror(errno));
    return -1;
}

static void state_path(const char *dir, char *buf, size_t n)
{
    snprintf(buf, n, "%s/%s", dir, STATE_NAME);
}

/* Tolerant scanner: we only ever read our own JSON, so look up known keys. */
static int json_find_string(const char *json, const char *key, char *out, size_t n)
{
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p)
        return -1;
    p = strchr(p + strlen(pat), ':');
    if (!p)
        return -1;
    p++;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    if (*p != '"')
        return -1;
    p++;
    size_t i = 0;
    while (*p && *p != '"' && i + 1 < n)
        out[i++] = *p++;
    out[i] = '\0';
    return 0;
}

static int json_find_int(const char *json, const char *key, int *out)
{
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p)
        return -1;
    p = strchr(p + strlen(pat), ':');
    if (!p)
        return -1;
    p++;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    char *end = NULL;
    long v = strtol(p, &end, 10);
    if (end == p)
        return -1;
    *out = (int)v;
    return 0;
}

static int state_load(const char *dir, struct state *st)
{
    state_default(st);
    char path[512];
    state_path(dir, path, sizeof(path));
    FILE *fh = fopen(path, "rb");
    if (!fh)
        return 0; /* missing state means "first boot of slot A" */
    char buf[1024];
    size_t n = fread(buf, 1, sizeof(buf) - 1, fh);
    fclose(fh);
    buf[n] = '\0';

    char slot[8];
    if (json_find_string(buf, "slot", slot, sizeof(slot)) == 0 && (slot[0] == 'A' || slot[0] == 'B'))
        st->slot[0] = slot[0];
    json_find_int(buf, "attempts", &st->attempts);
    json_find_int(buf, "rollback", &st->rollback);
    json_find_int(buf, "generation", &st->generation);
    if (st->attempts < 0)
        st->attempts = 0;
    return 0;
}

static int state_save(const char *dir, const struct state *st)
{
    if (ensure_dir(dir) != 0)
        return -1;
    char path[512], tmp[540];
    state_path(dir, path, sizeof(path));
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);

    FILE *fh = fopen(tmp, "wb");
    if (!fh) {
        fprintf(stderr, "updatr: cannot write %s: %s\n", tmp, strerror(errno));
        return -1;
    }
    fprintf(fh,
            "{\n  \"attempts\": %d,\n  \"generation\": %d,\n"
            "  \"rollback\": %s,\n  \"slot\": \"%s\"\n}\n",
            st->attempts, st->generation, st->rollback ? "true" : "false", st->slot);
    fflush(fh);
    if (fsync(fileno(fh)) != 0) {
        fclose(fh);
        return -1;
    }
    fclose(fh);
    if (rename(tmp, path) != 0) {
        fprintf(stderr, "updatr: rename failed: %s\n", strerror(errno));
        return -1;
    }
    int dfd = open(dir, O_RDONLY | O_DIRECTORY);
    if (dfd >= 0) {
        fsync(dfd);
        close(dfd);
    }
    return 0;
}

static void state_print(const struct state *st)
{
    printf("{\n  \"attempts\": %d,\n  \"generation\": %d,\n"
           "  \"rollback\": %s,\n  \"slot\": \"%s\"\n}\n",
           st->attempts, st->generation, st->rollback ? "true" : "false", st->slot);
}

static void state_other(const char *slot, char *out)
{
    out[0] = (slot[0] == 'A') ? 'B' : 'A';
    out[1] = '\0';
}

static void state_begin(struct state *st, int max_attempts)
{
    st->attempts++;
    if (st->attempts > max_attempts) {
        char other[2];
        state_other(st->slot, other);
        st->slot[0] = other[0];
        st->attempts = 0;
        st->rollback = 1;
        st->generation++;
    }
}

static int valid_slot(const char *s)
{
    return s && (s[0] == 'A' || s[0] == 'B') && s[1] == '\0';
}

static long long file_size(const char *path)
{
    struct stat sb;
    if (stat(path, &sb) != 0)
        return -1;
    return (long long)sb.st_size;
}

/* Copy a rootfs image into a slot device (or a regular file in tests). */
static int slot_install(const char *src, const char *dst)
{
    long long src_size = file_size(src);
    if (src_size <= 0) {
        fprintf(stderr, "updatr: cannot stat %s: %s\n", src, strerror(errno));
        return 2;
    }
    long long dst_size = file_size(dst);
    if (dst_size > 0 && dst_size < src_size) {
        fprintf(stderr, "updatr: target %s is %lld B, image is %lld B\n", dst, dst_size, src_size);
        return 4;
    }

    int in = open(src, O_RDONLY);
    if (in < 0) {
        fprintf(stderr, "updatr: open %s: %s\n", src, strerror(errno));
        return 2;
    }
    int out = open(dst, O_WRONLY);
    if (out < 0) {
        fprintf(stderr, "updatr: open %s: %s\n", dst, strerror(errno));
        close(in);
        return 2;
    }

    char buf[65536];
    long long written = 0;
    for (;;) {
        ssize_t n = read(in, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EINTR)
                continue;
            fprintf(stderr, "updatr: read: %s\n", strerror(errno));
            close(in);
            close(out);
            return 2;
        }
        if (n == 0)
            break;
        ssize_t off = 0;
        while (off < n) {
            ssize_t w = write(out, buf + off, (size_t)(n - off));
            if (w < 0) {
                if (errno == EINTR)
                    continue;
                fprintf(stderr, "updatr: write: %s\n", strerror(errno));
                close(in);
                close(out);
                return 2;
            }
            off += w;
        }
        written += n;
    }
    close(in);
    if (fsync(out) != 0) {
        fprintf(stderr, "updatr: fsync: %s\n", strerror(errno));
        close(out);
        return 2;
    }
    close(out);
    printf("{\"installed\": %lld, \"slot\": \"%s\"}\n", written, dst);
    return 0;
}

/* Points extlinux.conf at the given slot. The bootloader cannot read JSON, so the
 * only durable place for "which rootfs to mount" is the loader config itself. */
static int sync_boot(const char *boot_dir, const char *slot)
{
    char path[1400];
    char tmp[1400];
    char want[32];
    char text[8192];
    size_t len = 0;

    if (!boot_dir)
        return 0;
    snprintf(path, sizeof(path), "%s/extlinux/extlinux.conf", boot_dir);
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    snprintf(want, sizeof(want), "root=LABEL=DEEPOS_%s", slot);

    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "updatr: %s: %s\n", path, strerror(errno));
        return 2;
    }
    len = fread(text, 1, sizeof(text) - 1, f);
    fclose(f);
    text[len] = '\0';

    int changed = 0;
    const char *needles[2] = { "root=LABEL=DEEPOS_A", "root=LABEL=DEEPOS_B" };
    for (int i = 0; i < 2; i++) {
        char *at = strstr(text, needles[i]);
        if (!at)
            continue;
        size_t nlen = strlen(needles[i]);
        char out[8192];
        size_t head = (size_t)(at - text);
        if (head + strlen(want) >= sizeof(out))
            return 2;
        memcpy(out, text, head);
        memcpy(out + head, want, strlen(want));
        snprintf(out + head + strlen(want), sizeof(out) - head - strlen(want), "%s", at + nlen);
        snprintf(text, sizeof(text), "%s", out);
        changed = 1;
        break;
    }
    if (!changed) {
        fprintf(stderr, "updatr: %s has no root=LABEL=DEEPOS_A/B line\n", path);
        return 2;
    }

    FILE *o = fopen(tmp, "wb");
    if (!o) {
        fprintf(stderr, "updatr: %s: %s\n", tmp, strerror(errno));
        return 2;
    }
    size_t n = strlen(text);
    if (fwrite(text, 1, n, o) != n) {
        fclose(o);
        return 2;
    }
    fflush(o);
    if (fsync(fileno(o)) != 0) {
        fclose(o);
        return 2;
    }
    fclose(o);
    if (rename(tmp, path) != 0) {
        fprintf(stderr, "updatr: rename: %s\n", strerror(errno));
        return 2;
    }
    printf("{\"boot\": \"%s\", \"slot\": \"%s\"}\n", path, slot);
    return 0;
}

static void usage(void)
{
    fprintf(stderr,
            "usage: updatr --state DIR {status|decide|begin|good|switch A|B}\n"
            "       updatr --state DIR begin [--max-attempts N]\n"
            "       updatr --state DIR --boot DIR switch A|B\n"
            "       updatr --state DIR install --slot A|B --file IMG --dev TARGET\n");
}

int main(int argc, char **argv)
{
    const char *state_dir = NULL;
    const char *cmd = NULL;
    const char *slot = NULL;
    const char *file = NULL;
    const char *dev = NULL;
    const char *boot_dir = NULL;
    int max_attempts = MAX_ATTEMPTS;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--state") == 0 && i + 1 < argc) {
            state_dir = argv[++i];
        } else if (strcmp(argv[i], "--max-attempts") == 0 && i + 1 < argc) {
            max_attempts = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--slot") == 0 && i + 1 < argc) {
            slot = argv[++i];
        } else if (strcmp(argv[i], "--file") == 0 && i + 1 < argc) {
            file = argv[++i];
        } else if (strcmp(argv[i], "--dev") == 0 && i + 1 < argc) {
            dev = argv[++i];
        } else if (strcmp(argv[i], "--boot") == 0 && i + 1 < argc) {
            boot_dir = argv[++i];
        } else if (!cmd) {
            cmd = argv[i];
        } else if (!slot) {
            slot = argv[i];
        } else {
            usage();
            return 3;
        }
    }

    if (!state_dir || !cmd) {
        usage();
        return 3;
    }

    struct state st;
    state_load(state_dir, &st);

    if (strcmp(cmd, "status") == 0) {
        state_print(&st);
        return 0;
    }
    if (strcmp(cmd, "decide") == 0) {
        printf("%s\n", st.slot);
        return 0;
    }
    if (strcmp(cmd, "begin") == 0) {
        state_begin(&st, max_attempts);
        if (state_save(state_dir, &st) != 0)
            return 2;
        if (sync_boot(boot_dir, st.slot) != 0)
            return 2;
        state_print(&st);
        return 0;
    }
    if (strcmp(cmd, "good") == 0) {
        st.attempts = 0;
        st.rollback = 0;
        if (state_save(state_dir, &st) != 0)
            return 2;
        state_print(&st);
        return 0;
    }
    if (strcmp(cmd, "switch") == 0) {
        if (!valid_slot(slot)) {
            fprintf(stderr, "updatr: switch requires A or B\n");
            return 3;
        }
        st.slot[0] = slot[0];
        st.attempts = 0;
        st.rollback = 0;
        st.generation++;
        if (state_save(state_dir, &st) != 0)
            return 2;
        if (sync_boot(boot_dir, st.slot) != 0)
            return 2;
        state_print(&st);
        return 0;
    }
    if (strcmp(cmd, "install") == 0) {
        if (!valid_slot(slot) || !file || !dev) {
            fprintf(stderr, "updatr: install requires --slot A|B --file IMG --dev TARGET\n");
            return 3;
        }
        int rc = slot_install(file, dev);
        if (rc != 0)
            return rc;
        st.slot[0] = slot[0];
        st.attempts = 0;
        st.rollback = 0;
        st.generation++;
        if (state_save(state_dir, &st) != 0)
            return 2;
        state_print(&st);
        return 0;
    }

    usage();
    return 3;
}
