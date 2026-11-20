/* DEEPoS launcher - modd client (NDJSON request/reply over AF_UNIX). */
#include "dp_modc.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define MODC_MAX_LINE 8192

static int connect_socket(const char *path)
{
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0)
        return -1;
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    if (strlen(path) >= sizeof(addr.sun_path)) {
        close(fd);
        return -1;
    }
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", path);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int read_line(int fd, char *buf, size_t n)
{
    size_t used = 0;
    while (used + 1 < n) {
        ssize_t r = read(fd, buf + used, 1);
        if (r == 0)
            break;
        if (r < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (buf[used] == '\n') {
            buf[used] = '\0';
            return (int)used;
        }
        used++;
    }
    buf[used] = '\0';
    return (int)used;
}

int dp_modc_call(const char *socket_path, const char *method, const char *params,
                 char *out, size_t out_len)
{
    if (!socket_path || !method || !params || !out || out_len < 8)
        return -1;
    int fd = connect_socket(socket_path);
    if (fd < 0)
        return -1;

    char req[MODC_MAX_LINE];
    int len = snprintf(req, sizeof(req), "{\"id\":1,\"method\":\"%s\",\"params\":%s}\n", method,
                       params);
    if (len <= 0 || len >= (int)sizeof(req)) {
        close(fd);
        return -1;
    }
    if (write(fd, req, (size_t)len) != len) {
        close(fd);
        return -1;
    }

    char line[MODC_MAX_LINE];
    if (read_line(fd, line, sizeof(line)) < 0) {
        close(fd);
        return -1;
    }
    close(fd);

    const char *err = strstr(line, "\"error\"");
    if (err) {
        snprintf(out, out_len, "%.*s", (int)(out_len - 1), line);
        return -1;
    }
    const char *res = strstr(line, "\"result\"");
    if (!res) {
        snprintf(out, out_len, "%.*s", (int)(out_len - 1), line);
        return -1;
    }
    snprintf(out, out_len, "%s", res + strlen("\"result\":"));
    return 0;
}

/* Copies a JSON string body starting at p (points at '"') into dst. */
static int take_string(const char *p, char *dst, size_t dst_len, const char **next)
{
    if (*p != '"')
        return -1;
    p++;
    size_t used = 0;
    while (*p && *p != '"') {
        char ch = *p;
        if (*p == '\\' && p[1]) {
            p++;
            ch = *p;
            if (ch == 'n')
                ch = '\n';
            else if (ch == 'u' && strspn(p + 1, "0123456789abcdefABCDEF") >= 4) {
                ch = ' ';
                p += 4;
            }
        }
        if (used + 1 < dst_len)
            dst[used++] = ch;
        p++;
    }
    if (*p != '"')
        return -1;
    if (dst_len)
        dst[used] = '\0';
    if (next)
        *next = p + 1;
    return 0;
}

static int get_string(const char *json, const char *key, char *out, size_t size)
{
    const char *field = strstr(json, key);
    return field ? take_string(field + strlen(key), out, size, NULL) : -1;
}

int dp_modc_set_enabled(const char *socket_path, const char *module_id, int enabled)
{
    char params[128], payload[128];
    snprintf(params, sizeof(params), "{\"module\":\"%s\",\"enabled\":%d}", module_id, !!enabled);
    if (dp_modc_call(socket_path, "module.set_enabled", params, payload, sizeof(payload)) != 0)
        return -1;
    return strstr(payload, enabled ? "\"enabled\":true" : "\"enabled\":false") ? 0 : -1;
}

int dp_modc_describe(const char *socket_path, const char *module_id, char *out, size_t size)
{
    char params[128], payload[DP_MOD_TEXT * 6 + 64];
    snprintf(params, sizeof(params), "{\"module\":\"%s\"}", module_id);
    if (dp_modc_call(socket_path, "module.describe", params, payload, sizeof(payload)) != 0)
        return -1;
    return get_string(payload, "\"description\":", out, size);
}

int dp_modc_inspect(const char *socket_path, const char *module_id, char *out, size_t size)
{
    char params[128], payload[DP_MOD_TEXT * 6 + 128];
    snprintf(params, sizeof(params), "{\"module\":\"%s\",\"action\":\"inspect\"}", module_id);
    if (dp_modc_call(socket_path, "action.invoke", params, payload, sizeof(payload)) != 0)
        return -1;
    return get_string(payload, "\"message\":", out, size);
}

int dp_modc_action(const char *socket_path, const char *module_id, const char *action)
{
    char params[256];
    int n = snprintf(params, sizeof(params), "{\"module\":\"%s\",\"action\":\"%s\"}",
                     module_id, action);
    if (n <= 0 || n >= (int)sizeof(params))
        return -1;
    char payload[MODC_MAX_LINE];
    if (dp_modc_call(socket_path, "action.invoke", params, payload, sizeof(payload)) != 0)
        return -1;
    return strstr(payload, "\"ok\":true") ? 0 : -1;
}

int dp_modc_launch(const char *socket_path, const char *system, const char *rom,
                   int *allow)
{
    char params[512];
    char payload[MODC_MAX_LINE];
    int n = snprintf(params, sizeof(params),
                     "{\"system\":\"%s\",\"rom\":\"%s\"}", system, rom);
    if (n <= 0 || n >= (int)sizeof(params))
        return -1;
    if (dp_modc_call(socket_path, "launch.before", params, payload, sizeof(payload)) != 0)
        return -1;
    if (allow)
        *allow = strstr(payload, "\"allow\":false") ? 0 : 1;
    return 0;
}

int dp_modc_status(const char *socket_path, struct dp_model *m)
{
    char payload[MODC_MAX_LINE];
    if (dp_modc_call(socket_path, "status", "{}", payload, sizeof(payload)) != 0)
        return -1;

    m->nmods = 0;
    char *mods = strstr(payload, "\"modules\":[");
    if (!mods)
        return -1;
    char *p = mods + strlen("\"modules\":[");
    while (*p == '{' && m->nmods < DP_MAX_MODULES) {
        const char *end = p + 1;
        while (*end && *end != '}') {
            if (*end == '"') {
                if (take_string(end, NULL, 0, &end) != 0)
                    return -1;
            } else {
                end++;
            }
        }
        if (*end != '}')
            return -1;
        char *next = p + (end - p);
        *next++ = '\0';
        struct dp_module_info *mi = &m->mods[m->nmods];
        memset(mi, 0, sizeof(*mi));
        if (get_string(p, "\"id\":", mi->id, sizeof(mi->id)) != 0)
            return -1;
        if (get_string(p, "\"state\":", mi->state, sizeof(mi->state)) != 0)
            snprintf(mi->state, sizeof(mi->state), "unknown");
        get_string(p, "\"name\":", mi->name, sizeof(mi->name));
        mi->enabled = !strstr(p, "\"enabled\":false");
        mi->on_demand = strstr(p, "\"on_demand\":true") != NULL;
        m->nmods++;
        p = *next == ',' ? next + 1 : next;
    }
    return 0;
}
