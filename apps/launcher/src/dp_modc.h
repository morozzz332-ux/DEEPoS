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
int dp_modc_call(const char *socket_path, const char *method, const char *params,
                 char *out, size_t out_len);

#endif /* DP_MODC_H */
