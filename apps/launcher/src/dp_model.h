/* DEEPoS launcher - data model: library, continue list, status bar. */
#ifndef DP_MODEL_H
#define DP_MODEL_H

#include <stddef.h>

#define DP_MAX_SYSTEMS 160
#define DP_MAX_CONTINUE 12
#define DP_SYS_ID 24
#define DP_SYS_NAME 40
#define DP_TITLE_LEN 64
#define DP_MAX_MODULES 8
#define DP_MOD_ID 32
#define DP_MOD_STATE 16

struct dp_system {
    char id[DP_SYS_ID];       /* directory name, lower-case */
    char name[DP_SYS_NAME];   /* human readable */
    unsigned games;
};

struct dp_continue_item {
    char title[DP_TITLE_LEN];
    char system[DP_SYS_NAME];
    char meta[24];            /* "12 мин", "вчера" */
    int slot;                 /* -1 = no save */
    int has_save;
    char sys_id[32];          /* folder id, e.g. "md" */
    char rom[64];             /* file name inside the system folder */
};

struct dp_module_info {
    char id[DP_MOD_ID];       /* module id from module.toml */
    char state[DP_MOD_STATE]; /* ready / stopped / disabled / unknown */
};

struct dp_status {
    int battery;              /* percent, 0..100 */
    int charging;
    char clock[8];            /* "14:32" */
};

struct dp_model {
    struct dp_system systems[DP_MAX_SYSTEMS];
    int nsys;
    unsigned total_games;

    struct dp_continue_item cont[DP_MAX_CONTINUE];
    int ncont;

    struct dp_module_info mods[DP_MAX_MODULES];
    int nmods;

    struct dp_status st;

    /* storage, in megabytes, filled by the caller */
    unsigned rom_used_mb;
    unsigned rom_total_mb;
};

struct dp_model *dp_model_new(void);
void dp_model_free(struct dp_model *m);

/* Counts ROM files per system directory. Returns number of systems found or -1. */
int dp_model_scan(struct dp_model *m, const char *roms_dir);

/* Reads "<title>\t<system>\t<meta>\t<slot>\t<save>" lines; missing file is not an error. */
int dp_model_load_continue(struct dp_model *m, const char *data_dir);

/* Pretty name for a system id (falls back to the id itself). */
void dp_system_name(const char *id, char *out, size_t out_len);

#endif /* DP_MODEL_H */
