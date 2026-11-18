/* DEEPoS - minimal JSON helpers for the module transport.
 *
 * Not a general parser: the supervisor protocol uses flat, well-known keys, so
 * scanning for a key and taking the value right after it is enough and keeps
 * this file small enough to audit.
 */
#ifndef DP_JSON_H
#define DP_JSON_H

#include <stddef.h>

/* Copy the string value of `key` into out (NUL-terminated). Returns 1 on
 * success, 0 when the key is missing or malformed. Escapes are unescaped for
 * \" \\ \n \t and \uXXXX is replaced with '?'. */
int dp_json_get_str(const char *json, const char *key, char *out, size_t n);

/* Copy an integer value of `key`. Returns 1 on success. */
int dp_json_get_int(const char *json, const char *key, long *out);

/* Returns 1 when the object contains the key at all. */
int dp_json_has(const char *json, const char *key);

/* Write a JSON string literal (quotes included) into out. Returns bytes written
 * or 0 when out is too small. */
size_t dp_json_escape(const char *in, char *out, size_t n);

#endif /* DP_JSON_H */
