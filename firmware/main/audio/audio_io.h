/*
 * firmware/main/audio/audio_io.h — Hardware I2S driver for INMP441 mic and MAX98357A amp.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

class AudioIO {
public:
    static bool init();
    static size_t read_mic_mono16(int16_t* dst, size_t samples, uint32_t wait_ms = 20);
    static size_t write_spk_mono16(const int16_t* src, size_t samples, uint32_t wait_ms = 20);
    static void write_spk_silence(size_t samples);
    static void zero_spk_dma();
    static void set_mic_muted(bool muted);
    static bool is_mic_muted();
};

