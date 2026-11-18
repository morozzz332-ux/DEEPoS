/* DEEPoS - module transport implementation. */
#include "dp_module.h"
#include "dp_json.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define FAIL_WINDOW_S 600

static long now_s(void)
{
    return (long)time(NULL);
}

static void trim(char *s)
{
    size_t n = strlen(s);
    while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\r' || s[n - 1] == '\n'))
        s[--n] = '\0';
}

/* Strips surrounding quotes from a TOML string value. */
static void unquote(char *s)
{
    size_t n = strlen(s);
    if (n >= 2 && s[0] == '"' && s[n - 1] == '"') {
        memmove(s, s + 1, n - 2);
        s[n - 2] = '\0';
    }
}

int dp_module_load(struct dp_module *m, const char *dir)
{
    char path[600];
    FILE *f;
    char line[512];

    memset(m, 0, sizeof(*m));
    m->fd_in = -1;
    m->fd_out = -1;
    m->state = MODD_STOPPED;
    m->memory_mb = 32;
    snprintf(m->dir, sizeof(m->dir), "%s", dir);

    if (snprintf(path, sizeof(path), "%s/module.toml", dir) >= (int)sizeof(path))
        return -1;
    f = fopen(path, "r");
    if (!f)
        return -1;

    while (fgets(line, sizeof(line), f)) {
        char *eq;
        trim(line);
        if (!line[0] || line[0] == '#' || line[0] == '[')
            continue;
        eq = strchr(line, '=');
        if (!eq)
            continue;
        *eq = '\0';
        trim(line);
        char *value = eq + 1;
        while (*value == ' ' || *value == '\t')
            value++;
        trim(value);
        unquote(value);

        if (!strcmp(line, "id"))
            snprintf(m->id, sizeof(m->id), "%s", value);
        else if (!strcmp(line, "entry"))
            snprintf(m->entry, sizeof(m->entry), "%s", value);
        else if (!strcmp(line, "runtime"))
            snprintf(m->runtime, sizeof(m->runtime), "%s", value);
        else if (!strcmp(line, "memory_mb"))
            m->memory_mb = atoi(value);
        else if (!strcmp(line, "enabled"))
            m->enabled = strcmp(value, "false") != 0;
    }
    fclose(f);

    if (!m->id[0] || !m->entry[0])
        return -1;
    return 0;
}

int dp_module_start(struct dp_module *m, const char *data_dir)
{
    int to_child[2];
    int from_child[2];
    pid_t pid;
    char data_path[600];

    if (m->state == MODD_DISABLED)
        return -1;
    if (m->pid > 0)
        return 0;

    if (pipe(to_child) != 0)
        return -1;
    if (pipe(from_child) != 0) {
        close(to_child[0]);
        close(to_child[1]);
        return -1;
    }

    pid = fork();
    if (pid < 0) {
        close(to_child[0]);
        close(to_child[1]);
        close(from_child[0]);
        close(from_child[1]);
        return -1;
    }

    if (pid == 0) {
        /* child: stdin <- to_child[0], stdout -> from_child[1] */
        dup2(to_child[0], STDIN_FILENO);
        dup2(from_child[1], STDOUT_FILENO);
        close(to_child[0]);
        close(to_child[1]);
        close(from_child[0]);
        close(from_child[1]);
        if (chdir(m->dir) != 0)
            _exit(127);
        snprintf(data_path, sizeof(data_path), "%s/%s", data_dir, m->id);
        mkdir(data_path, 0700);
        setenv("MODD_MODULE_ID", m->id, 1);
        setenv("MODD_MODULE_DIR", m->dir, 1);
        setenv("MODD_MODULE_DATA", data_path, 1);
        setenv("ARCHR_MODULE_DATA", data_path, 1);
        execl("/bin/sh", "sh", "-c", m->entry, (char *)NULL);
        _exit(127);
    }

    close(to_child[0]);
    close(from_child[1]);
    fcntl(from_child[0], F_SETFL, O_NONBLOCK);

    m->pid = pid;
    m->fd_in = to_child[1];
    m->fd_out = from_child[0];
    m->line_len = 0;
    m->buf_len = 0;
    m->starts++;
    m->state = MODD_STARTING;
    return 0;
}

void dp_module_stop(struct dp_module *m)
{
    if (m->pid <= 0) {
        if (m->fd_in >= 0)
            close(m->fd_in);
        if (m->fd_out >= 0)
            close(m->fd_out);
        m->fd_in = m->fd_out = -1;
        return;
    }
    kill(m->pid, SIGTERM);
    for (int i = 0; i < 20; i++) {
        int status = 0;
        pid_t r = waitpid(m->pid, &status, WNOHANG);
        if (r == m->pid)
            goto closed;
        struct timespec ts = {0, 50 * 1000 * 1000};
        nanosleep(&ts, NULL);
    }
    kill(m->pid, SIGKILL);
    waitpid(m->pid, NULL, 0);
closed:
    if (m->fd_in >= 0)
        close(m->fd_in);
    if (m->fd_out >= 0)
        close(m->fd_out);
    m->fd_in = m->fd_out = -1;
    m->pid = 0;
    if (m->state != MODD_DISABLED)
        m->state = MODD_STOPPED;
}

int dp_module_poll_exit(struct dp_module *m)
{
    int status = 0;
    pid_t r;

    if (m->pid <= 0)
        return 0;
    r = waitpid(m->pid, &status, WNOHANG);
    if (r != m->pid)
        return 0;

    if (m->fd_in >= 0) {
        close(m->fd_in);
        m->fd_in = -1;
    }
    if (m->fd_out >= 0) {
        close(m->fd_out);
        m->fd_out = -1;
    }
    m->pid = 0;
    if (m->state != MODD_DISABLED) {
        m->state = MODD_FAILED;
        snprintf(m->last_error, sizeof(m->last_error), "exited (%s %d)",
                 WIFEXITED(status) ? "code" : "signal",
                 WIFEXITED(status) ? WEXITSTATUS(status) : WTERMSIG(status));
    }
    return 1;
}

const char *dp_module_state_name(int state)
{
    switch (state) {
    case MODD_STOPPED: return "stopped";
    case MODD_STARTING: return "starting";
    case MODD_READY: return "ready";
    case MODD_FAILED: return "failed";
    case MODD_DISABLED: return "disabled";
    default: return "?";
    }
}

int dp_module_fail(struct dp_module *m, const char *why)
{
    long now = now_s();
    int kept = 0;

    snprintf(m->last_error, sizeof(m->last_error), "%s", why ? why : "failure");
    for (int i = 0; i < m->fail_n; i++) {
        if (now - m->fail_at[i] < FAIL_WINDOW_S)
            m->fail_at[kept++] = m->fail_at[i];
    }
    m->fail_n = kept;
    if (m->fail_n < MODD_MAX_FAIL)
        m->fail_at[m->fail_n++] = now;

    if (m->state != MODD_DISABLED)
        m->state = MODD_FAILED;
    if (m->fail_n >= 3)
        m->state = MODD_DISABLED;
    return m->state;
}

/* Reads one complete line from the module stdout into m->line (without '\n').
 * Returns 1 when a line is ready, 0 when there is nothing yet, -1 on EOF. */
static int read_line(struct dp_module *m, int timeout_ms)
{
    struct pollfd pfd;
    int rc;

    for (;;) {
        char *nl = memchr(m->buf, '\n', m->buf_len);
        if (nl) {
            size_t len = (size_t)(nl - m->buf);
            if (len >= sizeof(m->line))
                len = sizeof(m->line) - 1;
            memcpy(m->line, m->buf, len);
            m->line[len] = '\0';
            memmove(m->buf, m->buf + (nl - m->buf) + 1,
                    m->buf_len - (size_t)(nl - m->buf) - 1);
            m->buf_len -= (size_t)(nl - m->buf) + 1;
            m->line_len = len;
            return 1;
        }
        if (m->buf_len >= sizeof(m->buf) - 1) {
            m->buf_len = 0; /* drop an absurdly long line */
        }
        if (m->fd_out < 0)
            return -1;

        pfd.fd = m->fd_out;
        pfd.events = POLLIN;
        pfd.revents = 0;
        rc = poll(&pfd, 1, timeout_ms);
        if (rc == 0)
            return 0;
        if (rc < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        ssize_t got = read(m->fd_out, m->buf + m->buf_len,
                           sizeof(m->buf) - 1 - m->buf_len);
        if (got == 0)
            return -1;
        if (got < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK)
                continue;
            return -1;
        }
        m->buf_len += (size_t)got;
    }
}

int dp_module_request(struct dp_module *m, const char *method, const char *params,
                      int timeout_ms, char *out, size_t n)
{
    char req[MODD_MAX_LINE];
    char idbuf[24];
    long want_id;

    if (m->pid <= 0 || m->fd_in < 0)
        return -2;

    m->next_id++;
    want_id = m->next_id;
    snprintf(req, sizeof(req),
             "{\"jsonrpc\":\"2.0\",\"id\":%ld,\"method\":\"%s\",\"params\":%s}\n",
             want_id, method, params && params[0] ? params : "{}");

    if (write(m->fd_in, req, strlen(req)) != (ssize_t)strlen(req))
        return -2;

    snprintf(idbuf, sizeof(idbuf), "%ld", want_id);
    for (;;) {
        int rc = read_line(m, timeout_ms);
        long got_id = -1;
        if (rc < 0)
            return -2;
        if (rc == 0)
            return -1;
        if (dp_json_get_int(m->line, "id", &got_id) && got_id != want_id) {
            /* reply for an older request: keep waiting */
            continue;
        }
        if (dp_json_has(m->line, "error")) {
            if (out && n)
                snprintf(out, n, "%s", m->line);
            m->state = MODD_READY;
            return -3;
        }
        if (out && n)
            snprintf(out, n, "%s", m->line);
        m->state = MODD_READY;
        return 0;
    }
}
