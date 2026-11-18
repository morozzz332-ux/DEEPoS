/* DEEPoS - minimal JSON helpers (see dp_json.h for the contract). */
#include "dp_json.h"

#include <stdio.h>
#include <string.h>

/* Position of `"key"` inside json, or NULL. Skips escaped quotes. */
static const char *find_key(const char *json, const char *key)
{
    char pattern[96];
    if (!json || !key)
        return NULL;
    if (snprintf(pattern, sizeof(pattern), "\"%s\"", key) >= (int)sizeof(pattern))
        return NULL;
    return strstr(json, pattern);
}

static const char *skip_ws(const char *p)
{
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    return p;
}

int dp_json_has(const char *json, const char *key)
{
    return find_key(json, key) != NULL;
}

int dp_json_get_int(const char *json, const char *key, long *out)
{
    const char *p = find_key(json, key);
    long value = 0;
    int sign = 1;
    int any = 0;

    if (!p)
        return 0;
    p = skip_ws(p + strlen(key) + 2);
    if (*p != ':')
        return 0;
    p = skip_ws(p + 1);
    if (*p == '-') {
        sign = -1;
        p++;
    }
    while (*p >= '0' && *p <= '9') {
        value = value * 10 + (*p - '0');
        any = 1;
        p++;
    }
    if (!any)
        return 0;
    if (out)
        *out = value * sign;
    return 1;
}

static const char *unescape(const char *p, char *out, size_t n)
{
    size_t used = 0;
    while (*p && *p != '"') {
        char ch = *p++;
        if (ch == '\\') {
            char esc = *p++;
            switch (esc) {
            case 'n': ch = '\n'; break;
            case 't': ch = '\t'; break;
            case 'r': ch = '\r'; break;
            case 'b': ch = '\b'; break;
            case 'f': ch = '\f'; break;
            case '/': ch = '/'; break;
            case '\\': ch = '\\'; break;
            case '"': ch = '"'; break;
            case 'u':
                /* keep the 4 hex digits as a single placeholder */
                p += 4;
                ch = '?';
                break;
            default: ch = esc; break;
            }
        }
        if (used + 1 < n)
            out[used++] = ch;
    }
    if (used < n)
        out[used] = '\0';
    return p;
}

int dp_json_get_str(const char *json, const char *key, char *out, size_t n)
{
    const char *p = find_key(json, key);
    if (!p || n == 0)
        return 0;
    p = skip_ws(p + strlen(key) + 2);
    if (*p != ':')
        return 0;
    p = skip_ws(p + 1);
    if (*p != '"')
        return 0;
    unescape(p + 1, out, n);
    return 1;
}

size_t dp_json_escape(const char *in, char *out, size_t n)
{
    size_t used = 0;
    if (n < 3)
        return 0;
    out[used++] = '"';
    for (const char *p = in; p && *p; p++) {
        unsigned char ch = (unsigned char)*p;
        const char *rep = NULL;
        char buf[8];
        switch (ch) {
        case '"': rep = "\\\""; break;
        case '\\': rep = "\\\\"; break;
        case '\n': rep = "\\n"; break;
        case '\t': rep = "\\t"; break;
        case '\r': rep = "\\r"; break;
        default:
            break;
        }
        if (ch < 0x20) {
            snprintf(buf, sizeof(buf), "\\u%04x", ch);
            rep = buf;
        }
        if (rep) {
            size_t len = strlen(rep);
            if (used + len + 2 >= n)
                return 0;
            memcpy(out + used, rep, len);
            used += len;
        } else {
            if (used + 2 >= n)
                return 0;
            out[used++] = (char)ch;
        }
    }
    out[used++] = '"';
    out[used] = '\0';
    return used;
}
