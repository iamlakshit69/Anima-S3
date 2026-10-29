/*
 * firmware/main/audio/cues.h — Acoustic feedback cues (wake chime, error, ready).
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

enum class CueType {
    WAKE,
    READY,
    ERROR
};

class Cues {
public:
    static void play(CueType type);
    static size_t generate_tone(int16_t* dst, size_t samples, float freq_hz, uint32_t sample_rate = 24000);
};

