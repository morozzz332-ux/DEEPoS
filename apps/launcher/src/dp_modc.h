/* DEEPoS launcher - client for the modd supervisor (NDJSON over a UNIX socket).
 *
 * The launcher only needs the module list for its "МОДУЛИ" screen, so this is a
 * minimal synchronous client: one status call per refresh, no caching.
 */
#ifndef DP_MODC_H
#define DP_MODC_H

#include "dp_model.h"

/* Fetches the module list into m->mods / m->nmods. Returns 0 on success,
 * -1 when the socket is unreachable or the reply is malformed. */
int dp_modc_status(const char *socket_path, struct dp_model *m);

/* Sends one method call with a JSON params object (may be "{}").
 * Writes the raw "result" payload into out. Returns 0 on success. */
/* Invokes one module action ("eco", "backup", ...). Returns 0 when the
 * supervisor accepted it, -1 when the call failed or modd reported an error. */
int dp_modc_action(const char *socket_path, const char *module_id, const char *action);
int dp_modc_set_enabled(const char *socket_path, const char *module_id, int enabled);
int dp_modc_describe(const char *socket_path, const char *module_id, char *out, size_t size);
int dp_modc_inspect(const char *socket_path, const char *module_id, char *out, size_t size);

/* Asks every module for its launch decision. Returns 0 when the call went
 * through (allow is 1 or 0), -1 when the supervisor is unreachable (allow
 * stays 1: modules are advisory, they must not block play when absent). */
int dp_modc_launch(const char *socket_path, const char *system, const char *rom,
                   int *allow);

int dp_modc_call(const char *socket_path, const char *method, const char *params,
                 char *out, size_t out_len);

#endif /* DP_MODC_H */
