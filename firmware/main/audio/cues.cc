/*
 * firmware/main/audio/cues.cc — Audio cue generator implementation.
 */

#include "audio/cues.h"
#include "audio/audio_io.h"
#include "config.h"
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

size_t Cues::generate_tone(int16_t* dst, size_t samples, float freq_hz, uint32_t sample_rate) {
    if (!dst || samples == 0) return 0;
    double step = (2.0 * M_PI * freq_hz) / static_cast<double>(sample_rate);
    for (size_t i = 0; i < samples; ++i) {
        // Apply smooth envelope (fade in/out 10ms)
        double env = 1.0;
        size_t fade = sample_rate * 10 / 1000;
        if (i < fade) {
            env = static_cast<double>(i) / fade;
        } else if (i + fade >= samples) {
            env = static_cast<double>(samples - 1 - i) / fade;
        }
        dst[i] = static_cast<int16_t>(sin(i * step) * env * 10000.0);
    }
    return samples;
}

void Cues::play(CueType type) {
    int16_t tone_buf[CONFIG_AUDIO_DN_RATE / 5]; // 200ms buffer
    size_t samples = 0;

    switch (type) {
        case CueType::WAKE:
            // 880 Hz (A5) cheerful wake ping (120ms)
            samples = CONFIG_AUDIO_DN_RATE * 120 / 1000;
            generate_tone(tone_buf, samples, 880.0f, CONFIG_AUDIO_DN_RATE);
            AudioIO::write_spk_mono16(tone_buf, samples);
            break;

        case CueType::READY:
            // Double pip: 587 Hz (100ms)
            samples = CONFIG_AUDIO_DN_RATE * 100 / 1000;
            generate_tone(tone_buf, samples, 587.33f, CONFIG_AUDIO_DN_RATE);
            AudioIO::write_spk_mono16(tone_buf, samples);
            break;

        case CueType::ERROR:
            // Low error buzz: 220 Hz (200ms)
            samples = CONFIG_AUDIO_DN_RATE * 200 / 1000;
            generate_tone(tone_buf, samples, 220.0f, CONFIG_AUDIO_DN_RATE);
            AudioIO::write_spk_mono16(tone_buf, samples);
            break;
    }
}

