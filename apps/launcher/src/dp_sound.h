#ifndef DP_SOUND_H
#define DP_SOUND_H

#include <sys/types.h>

enum dp_tone { DP_TONE_TAB, DP_TONE_CONFIRM, DP_TONE_BACK };

pid_t dp_sound_play(pid_t active, enum dp_tone tone);
void dp_sound_stop(pid_t active);

#endif
