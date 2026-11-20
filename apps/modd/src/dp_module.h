/* DEEPoS - module transport: one child process speaking NDJSON JSON-RPC. */
#ifndef DP_MODULE_H
#define DP_MODULE_H

#include <sys/types.h>
#include <stddef.h>

#define MODD_MAX_LINE 8192
#define MODD_MAX_FAIL 8

enum modd_state {
    MODD_STOPPED = 0,
    MODD_STARTING,
    MODD_READY,
    MODD_FAILED,
    MODD_DISABLED
};

struct dp_module {
    char id[48];
    char name[96];
    char description[256];
    char dir[512];
    char entry[512];
    char runtime[24];
    int memory_mb;
    int enabled;
    int on_demand;

    pid_t pid;
    int fd_in;
    int fd_out;

    char line[MODD_MAX_LINE];
    size_t line_len;
    char buf[MODD_MAX_LINE]; /* unread bytes of the last read() */
    size_t buf_len;

    long next_id;
    int state;
    int starts;
    long fail_at[MODD_MAX_FAIL];
    int fail_n;
    char last_error[160];
};

/* Load <dir>/module.toml. Returns 0 on success, -1 when the manifest is broken. */
int dp_module_load(struct dp_module *m, const char *dir);

/* Spawn the module entry point (bash/sh) and prepare the pipes. */
int dp_module_start(struct dp_module *m, const char *data_dir);

/* Terminate the child (SIGTERM, then SIGKILL after 1 s). */
void dp_module_stop(struct dp_module *m);

/* Reap: returns 1 when the child has exited, 0 when still running. */
int dp_module_poll_exit(struct dp_module *m);

/* Send a request and wait for the reply with the matching id.
 * Returns 0 on success (reply in `out`), -1 on timeout, -2 on transport error,
 * -3 when the reply carries an "error" object. */
int dp_module_request(struct dp_module *m, const char *method, const char *params,
                      int timeout_ms, char *out, size_t n);

/* Record a failure; three failures inside 10 minutes disable the module.
 * Returns the new state. */
int dp_module_fail(struct dp_module *m, const char *why);

const char *dp_module_state_name(int state);

#endif /* DP_MODULE_H */
