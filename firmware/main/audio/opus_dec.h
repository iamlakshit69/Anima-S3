/*
 * firmware/main/audio/opus_dec.h — Opus 24 kHz audio decoder for downlink frames.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

class OpusAudioDecoder {
public:
    OpusAudioDecoder();
    ~OpusAudioDecoder();

    bool init(uint32_t sample_rate = 24000);
    int decode(const uint8_t* pkt, size_t pkt_len, int16_t* out_pcm, size_t max_samples);
    void reset();

private:
    void* state_;
};
