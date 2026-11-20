/* DEEPoS launcher - data model: library, continue list, status bar. */
#ifndef DP_MODEL_H
#define DP_MODEL_H

#include <stddef.h>

#include "dp_input.h"
#include "dp_config.h"

#define DP_MAX_SYSTEMS 175
#define DP_MAX_CONTINUE 12
#define DP_SYS_ID 24
#define DP_SYS_NAME 40
#define DP_TITLE_LEN 64
#define DP_ROM_NAME 256
#define DP_MAX_MODULES 16
#define DP_MOD_ID 48
#define DP_MOD_STATE 16
#define DP_MOD_TEXT 256
#define DP_SETTINGS_CLOCK 12
#define DP_SETTINGS_REGION 13
#define DP_SETTINGS_EMULATORS 14
#define DP_SETTINGS_THEME 15
#define DP_SETTINGS_COUNT 16

enum dp_rom_source { DP_ROM_AUTO, DP_ROM_TF1, DP_ROM_TF2 };

struct dp_system {
    char id[DP_SYS_ID];       /* directory name, lower-case */
    char name[DP_SYS_NAME];   /* human readable */
    char folders[2][DP_SYS_ID + 5]; /* relative path on each card */
    char extensions[256];
    unsigned games;
    unsigned tf2_games;
};

struct dp_rom_item {
    char *name;
    enum dp_rom_source source;
};

struct dp_continue_item {
    char title[DP_TITLE_LEN];
    char system[DP_SYS_NAME];
    char meta[24];            /* "12 мин", "вчера" */
    int slot;                 /* -1 = no save */
    int has_save;
    char sys_id[32];          /* folder id, e.g. "md" */
    char rom[DP_ROM_NAME];    /* file name inside the system folder */
    enum dp_rom_source source;
};

struct dp_module_info {
    char id[DP_MOD_ID];       /* module id from module.toml */
    char state[DP_MOD_STATE]; /* ready / stopped / disabled / unknown */
    char name[96];
    int enabled;
    int on_demand;
};

struct dp_status {
    int battery;              /* percent, 0..100 */
    int charging;
    char clock[8];            /* "14:32" */
};

/* Real device facts for the "Сведения" screen and the boot report. Filled on
 * the device only; host renders show a dash instead of unstable data. */
#define DP_SYSINFO_FIELD 32
struct dp_sysinfo {
    char kernel[DP_SYSINFO_FIELD];   /* uname -r */
    unsigned long uptime_s;          /* seconds since boot, 0 = unknown */
    unsigned mem_total_mb;
    unsigned mem_avail_mb;
    int temp_mc;                     /* millidegrees C, 0 = unknown */
    char input[DP_INPUT_NAME];
    int input_events;
    char fb[DP_SYSINFO_FIELD];       /* "640x480 RGB565" */
    long cpu_khz, cpu_max_khz, gpu_hz;
    char last_key[16];
};

struct dp_model {
    struct dp_system systems[DP_MAX_SYSTEMS];
    int nsys;
    unsigned total_games;
    struct dp_rom_item *roms;  /* sorted files for the open system */
    int nroms;

    struct dp_continue_item cont[DP_MAX_CONTINUE];
    int ncont;

    struct dp_module_info mods[DP_MAX_MODULES];

    /* settings.toml, loaded by main(); 0 / "" mean "not set" */
    /* 1 when the runtime directory is usable right now */
    int data_ok;
    int roms_ok;
    int tf2_ok;
    const char *tf2_root;

    int cfg_brightness;
    int cfg_volume;
    enum dp_menu_sticks menu_sticks;
    int swap_menu_ab;
    char theme[DP_THEME_ID];
    int prefs[DP_PREF_COUNT];
    char usb_mode[12];
    char usb_link[24];
    char cfg_profile[16];
    char clock_date[16];
    int clock_zone;
    int nmods;
    int modules_online;

    struct dp_status st;
    struct dp_sysinfo si;
    int have_sysinfo;

    /* storage, in megabytes, filled by the caller */
    unsigned rom_used_mb;
    unsigned rom_total_mb;
};

struct dp_model *dp_model_new(void);
void dp_model_free(struct dp_model *m);

/* Counts ROM files per system directory. Returns number of systems found or -1. */
int dp_model_scan(struct dp_model *m, const char *roms_dir);
enum dp_rom_source dp_model_rom_path(const struct dp_model *m, const char *roms_dir,
                                     const char *id, const char *rom, enum dp_rom_source source,
                                     char *path, size_t size);
int dp_model_load_games(struct dp_model *m, const char *roms_dir, int system_index);

/* Reads "<title>\t<system>\t<meta>\t<slot>\t<save>" lines; missing file is not an error. */
int dp_model_load_continue(struct dp_model *m, const char *data_dir);

/* Pretty name for a system id (falls back to the id itself). */
void dp_system_name(const char *id, char *out, size_t out_len);

#endif /* DP_MODEL_H */
