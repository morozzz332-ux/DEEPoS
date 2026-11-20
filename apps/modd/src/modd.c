/* DEEPoS - modd: module supervisor (host prototype).
 *
 * Protocol: one NDJSON request per line on a UNIX socket.
 *   {"id":1,"method":"status"}
 *   {"id":2,"method":"initialize","params":{"module":"thermal"}}
 *   {"id":3,"method":"action.invoke","params":{"module":"thermal","action":"eco"}}
 *   {"id":5,"method":"launch.before","params":{"system":"md","rom":"g0.md"}}
 *   {"id":4,"method":"shutdown"}
 * Replies: {"id":N,"result":{...}} or {"id":N,"error":{"message":"..."}}.
 *
 * The launcher-facing API mirrors Arch-R modules api_version 3 so the same
 * module directories can be reused on both systems.
 */
#include "dp_json.h"
#include "dp_module.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define MAX_MODULES 16
#define MAX_CLIENTS 8
#define MODD_VERSION "0.1"

static struct dp_module g_mods[MAX_MODULES];
static int g_nmods;
static int g_running = 1;
static const char *g_data_dir = "/tmp/modd-data";

static int env_int(const char *name, int fallback)
{
    const char *v = getenv(name);
    return v && *v ? atoi(v) : fallback;
}

static int init_timeout_ms(void) { return env_int("MODD_INIT_MS", 10000); }
static int action_timeout_ms(void) { return env_int("MODD_ACTION_MS", 1000); }

static struct dp_module *find_module(const char *id)
{
    for (int i = 0; i < g_nmods; i++)
        if (!strcmp(g_mods[i].id, id))
            return &g_mods[i];
    return NULL;
}

static int enabled_path(char *path, size_t size, const char *id)
{
    int n = snprintf(path, size, "%s/.enabled-%s", g_data_dir, id);
    return n >= 0 && (size_t)n < size;
}

static void load_enabled(struct dp_module *m)
{
    char path[600];
    if (!enabled_path(path, sizeof(path), m->id))
        return;
    FILE *file = fopen(path, "r");
    if (file) {
        int value = fgetc(file);
        if ((value == '0' || value == '1') && fgetc(file) == '\n')
            m->enabled = value == '1';
        fclose(file);
    }
}

static int store_enabled(struct dp_module *m, int enabled)
{
    char path[600], temporary[620];
    const char value[] = { enabled ? '1' : '0', '\n' };
    if (!enabled_path(path, sizeof(path), m->id))
        return -1;
    snprintf(temporary, sizeof(temporary), "%s.XXXXXX", path);
    int fd = mkstemp(temporary);
    if (fd < 0)
        return -1;
    int ok = write(fd, value, sizeof(value)) == sizeof(value) && fsync(fd) == 0;
    if (close(fd) != 0)
        ok = 0;
    if (!ok || rename(temporary, path) != 0) {
        unlink(temporary);
        return -1;
    }
    if (!enabled || m->state == MODD_DISABLED) {
        dp_module_stop(m);
        m->state = MODD_STOPPED;
        m->fail_n = 0;
        m->last_error[0] = '\0';
    }
    m->enabled = enabled;
    return 0;
}

static void load_modules(const char *dir)
{
    DIR *d = opendir(dir);
    struct dirent *ent;

    if (!d) {
        fprintf(stderr, "modd: cannot open modules dir %s: %s\n", dir, strerror(errno));
        return;
    }
    while ((ent = readdir(d)) != NULL) {
        char path[600];
        struct dp_module m;
        if (ent->d_name[0] == '.')
            continue;
        if (g_nmods >= MAX_MODULES)
            break;
        snprintf(path, sizeof(path), "%s/%s", dir, ent->d_name);
        if (dp_module_load(&m, path) != 0) {
            fprintf(stderr, "modd: skip %s (bad manifest)\n", ent->d_name);
            continue;
        }
        if (strspn(m.id, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
                != strlen(m.id) || find_module(m.id)) {
            fprintf(stderr, "modd: invalid or duplicate module id in %s\n", ent->d_name);
            continue;
        }
        char imported[sizeof(m.dir) + 32];
        snprintf(imported, sizeof(imported), "%s/.deepos-roms-import", m.dir);
        if (access(imported, F_OK) == 0)
            m.enabled = 0;
        load_enabled(&m);
        g_mods[g_nmods++] = m;
        fprintf(stderr, "modd: loaded module %s (%s)\n", m.id, m.entry);
    }
    closedir(d);
}

static void status_json(char *out, size_t n)
{
    size_t used = 0;
    used += (size_t)snprintf(out + used, n - used, "{\"version\":\"%s\",\"modules\":[",
                             MODD_VERSION);
    for (int i = 0; i < g_nmods; i++) {
        const struct dp_module *m = &g_mods[i];
        char name[160], err[160], row[496];
        if (!dp_json_escape(m->name, name, sizeof(name)))
            strcpy(name, "\"\"");
        if (!dp_json_escape(m->last_error, err, sizeof(err)))
            strcpy(err, "\"\"");
        int length = snprintf(row, sizeof(row),
                              "%s{\"id\":\"%s\",\"state\":\"%s\",\"enabled\":%s,"
                              "\"on_demand\":%s,\"name\":%s,\"starts\":%d,"
                              "\"failures\":%d,\"last_error\":%s}",
                              i ? "," : "", m->id, dp_module_state_name(m->state),
                              m->enabled ? "true" : "false", m->on_demand ? "true" : "false",
                              name, m->starts, m->fail_n, err);
        if (length < 0 || (size_t)length >= sizeof(row) || (size_t)length + 3 > n - used)
            break;
        memcpy(out + used, row, (size_t)length);
        used += (size_t)length;
    }
    snprintf(out + used, n - used, "]}");
}

/* Starts a module and performs the initialize handshake. */
static int bring_up(struct dp_module *m)
{
    char reply[MODD_MAX_LINE];

    if (!m->enabled || m->state == MODD_DISABLED)
        return -1;
    if (m->pid > 0 && m->state == MODD_READY)
        return 0;
    dp_module_stop(m);
    if (dp_module_start(m, g_data_dir) != 0) {
        dp_module_fail(m, "cannot spawn");
        return -1;
    }
    if (dp_module_request(m, "initialize", "{\"api\":3}", init_timeout_ms(),
                          reply, sizeof(reply)) != 0) {
        dp_module_fail(m, "initialize failed");
        dp_module_stop(m);
        return -1;
    }
    m->state = MODD_READY;
    return 0;
}

static void stop_all(void)
{
    for (int i = 0; i < g_nmods; i++)
        dp_module_stop(&g_mods[i]);
}

static void handle_request(char *line, char *out, size_t out_n)
{
    long id = 0;
    char method[64] = "";
    char module_id[64] = "";
    char action[64] = "";

    if (!dp_json_get_int(line, "id", &id)) {
        snprintf(out, out_n, "{\"id\":0,\"error\":{\"message\":\"missing id\"}}");
        return;
    }
    if (!dp_json_get_str(line, "method", method, sizeof(method))) {
        snprintf(out, out_n, "{\"id\":%ld,\"error\":{\"message\":\"missing method\"}}", id);
        return;
    }

    if (!strcmp(method, "status")) {
        char payload[8000];
        status_json(payload, sizeof(payload));
        snprintf(out, out_n, "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":%s}", id, payload);
        return;
    }
    if (!strcmp(method, "shutdown")) {
        snprintf(out, out_n, "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"stopped\":true}}", id);
        g_running = 0;
        return;
    }
    if (!strcmp(method, "launch.before")) {
        const char *p = strstr(line, "\"params\"");
        char sys[32] = "", rom[256] = "";
        char params[512];
        int allow = 1, asked = 0;
        if (p) {
            dp_json_get_str(p, "system", sys, sizeof(sys));
            dp_json_get_str(p, "rom", rom, sizeof(rom));
        }
        snprintf(params, sizeof(params), "{\"system\":\"%s\",\"rom\":\"%s\"}", sys, rom);
        for (int i = 0; i < g_nmods; i++) {
            struct dp_module *m = &g_mods[i];
            char reply[MODD_MAX_LINE];
            if (!m->enabled || m->on_demand || m->state == MODD_DISABLED)
                continue;
            if (bring_up(m) != 0)
                continue;
            if (dp_module_request(m, "launch.before", params, action_timeout_ms(), reply,
                                  sizeof(reply)) == 0) {
                asked++;
                if (strstr(reply, "\"decision\":\"deny\""))
                    allow = 0;
            }
        }
        snprintf(out, out_n,
                 "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"allow\":%s,\"asked\":%d}}",
                 id, allow ? "true" : "false", asked);
        return;
    }
    if (dp_json_get_str(line, "module", module_id, sizeof(module_id)) == 0) {
        /* params are nested one level down in our wire format */
        const char *p = strstr(line, "\"params\"");
        if (p)
            dp_json_get_str(p, "module", module_id, sizeof(module_id));
    }

    struct dp_module *m = find_module(module_id);
    if (!m) {
        snprintf(out, out_n,
                 "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"message\":\"unknown module\"}}", id);
        return;
    }

    if (!strcmp(method, "module.set_enabled")) {
        long enabled;
        if (!dp_json_get_int(line, "enabled", &enabled) || (enabled != 0 && enabled != 1))
            snprintf(out, out_n,
                     "{\"id\":%ld,\"error\":{\"message\":\"expected enabled=0 or 1\"}}", id);
        else if (store_enabled(m, (int)enabled) != 0)
            snprintf(out, out_n,
                     "{\"id\":%ld,\"error\":{\"message\":\"cannot save module state\"}}", id);
        else
            snprintf(out, out_n, "{\"id\":%ld,\"result\":{\"enabled\":%s}}",
                     id, m->enabled ? "true" : "false");
        return;
    }
    if (!strcmp(method, "module.describe")) {
        char description[sizeof(m->description) * 6 + 3];
        dp_json_escape(m->description, description, sizeof(description));
        snprintf(out, out_n, "{\"id\":%ld,\"result\":{\"description\":%s}}", id, description);
        return;
    }

    if (!strcmp(method, "initialize")) {
        if (bring_up(m) == 0)
            snprintf(out, out_n,
                     "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"ready\":true,\"module\":\"%s\"}}",
                     id, m->id);
        else
            snprintf(out, out_n,
                     "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"message\":\"initialize failed\"}}",
                     id);
        if (m->on_demand)
            dp_module_stop(m);
        return;
    }

    if (!strcmp(method, "action.invoke")) {
        const char *p = strstr(line, "\"params\"");
        char params[MODD_MAX_LINE];
        char reply[MODD_MAX_LINE];
        int rc;
        if (p && dp_json_get_str(p, "action", action, sizeof(action)) == 0)
            action[0] = '\0';
        if (bring_up(m) != 0) {
            snprintf(out, out_n,
                     "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"message\":\"module not ready\"}}",
                     id);
            return;
        }
        snprintf(params, sizeof(params), "{\"action\":\"%s\"}", action);
        rc = dp_module_request(m, "action.invoke", params, action_timeout_ms(),
                               reply, sizeof(reply));
        if (m->on_demand)
            dp_module_stop(m);
        if (rc == 0) {
            char message[256] = "", escaped[sizeof(message) * 6 + 3];
            if (!dp_json_get_str(reply, "message", message, sizeof(message)))
                message[0] = '\0';
            dp_json_escape(message, escaped, sizeof(escaped));
            snprintf(out, out_n,
                     "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"result\":{\"ok\":true,\"module\":\"%s\","
                     "\"message\":%s}}", id, m->id, escaped);
        } else {
            dp_module_fail(m, rc == -1 ? "action timeout" : "action failed");
            snprintf(out, out_n,
                     "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"message\":\"%s\"}}",
                     id, rc == -1 ? "timeout" : "module error");
        }
        return;
    }

    snprintf(out, out_n, "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"error\":{\"message\":\"unknown method\"}}",
             id);
}

static int serve(const char *sock_path)
{
    struct sockaddr_un addr;
    int lfd, rc;

    unlink(sock_path);
    lfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (lfd < 0) {
        perror("modd: socket");
        return 1;
    }
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", sock_path);
    if (bind(lfd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        perror("modd: bind");
        close(lfd);
        return 1;
    }
    chmod(sock_path, 0600);
    if (listen(lfd, 8) != 0) {
        perror("modd: listen");
        close(lfd);
        return 1;
    }
    fprintf(stderr, "modd: listening on %s (%d modules)\n", sock_path, g_nmods);

    while (g_running) {
        struct pollfd pfd;
        int ready;
        int cfd;
        char buf[8192];
        size_t used = 0;

        pfd.fd = lfd;
        pfd.events = POLLIN;
        pfd.revents = 0;
        ready = poll(&pfd, 1, 200);
        for (int i = 0; i < g_nmods; i++)
            dp_module_poll_exit(&g_mods[i]);
        if (ready <= 0)
            continue;

        cfd = accept(lfd, NULL, NULL);
        if (cfd < 0)
            continue;

        for (;;) {
            ssize_t got;
            char *nl;
            struct pollfd cp = {cfd, POLLIN, 0};
            rc = poll(&cp, 1, 100);
            if (rc <= 0)
                break;
            got = read(cfd, buf + used, sizeof(buf) - 1 - used);
            if (got <= 0)
                break;
            used += (size_t)got;
            buf[used] = '\0';
            while ((nl = memchr(buf, '\n', used)) != NULL) {
                char line[8192];
                char out[8192];
                size_t len = (size_t)(nl - buf);
                if (len >= sizeof(line))
                    len = sizeof(line) - 1;
                memcpy(line, buf, len);
                line[len] = '\0';
                memmove(buf, nl + 1, used - len - 1);
                used -= len + 1;
                handle_request(line, out, sizeof(out));
                (void)write(cfd, out, strlen(out));
                (void)write(cfd, "\n", 1);
            }
            if (used >= sizeof(buf) - 1)
                used = 0;
        }
        close(cfd);
    }

    close(lfd);
    unlink(sock_path);
    return 0;
}

int main(int argc, char **argv)
{
    const char *modules_dir = NULL;
    const char *sock_path = NULL;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--modules") && i + 1 < argc)
            modules_dir = argv[++i];
        else if (!strcmp(argv[i], "--socket") && i + 1 < argc)
            sock_path = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc)
            g_data_dir = argv[++i];
        else if (!strcmp(argv[i], "--version")) {
            printf("modd %s\n", MODD_VERSION);
            return 0;
        } else {
            fprintf(stderr,
                    "usage: modd --modules DIR --socket PATH [--data DIR] [--version]\n");
            return 2;
        }
    }
    if (!modules_dir || !sock_path) {
        fprintf(stderr, "modd: --modules and --socket are required\n");
        return 2;
    }

    signal(SIGPIPE, SIG_IGN);
    mkdir(g_data_dir, 0700);
    load_modules(modules_dir);
    int rc = serve(sock_path);
    stop_all();
    return rc;
}
