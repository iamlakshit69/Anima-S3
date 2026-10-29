/*
 * firmware/main/audio/opus_enc.h — Opus 16 kHz audio encoder for uplink frames.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

class OpusAudioEncoder {
public:
    OpusAudioEncoder();
    ~OpusAudioEncoder();

    bool init(uint32_t sample_rate = 16000, uint32_t bitrate = 20000);
    int encode(const int16_t* pcm, size_t samples, uint8_t* out_pkt, size_t max_bytes);
    void reset();

private:
    void* state_;
};

