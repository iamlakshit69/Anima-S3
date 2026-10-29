/*
 * firmware/main/audio/opus_dec.cc — Opus decoder implementation.
 */

#include "audio/opus_dec.h"

#if defined(ESP_PLATFORM)
#include "opus.h"
#include "esp_log.h"
static const char* TAG = "opus_dec";
#endif

OpusAudioDecoder::OpusAudioDecoder() : state_(nullptr) {}

OpusAudioDecoder::~OpusAudioDecoder() {
    reset();
}

bool OpusAudioDecoder::init(uint32_t sample_rate) {
#if defined(ESP_PLATFORM)
    reset();
    int err = 0;
    OpusDecoder* dec = opus_decoder_create(sample_rate, 1, &err);
    if (err != OPUS_OK || !dec) {
        ESP_LOGE(TAG, "Failed to create Opus decoder: %d", err);
        return false;
    }
    state_ = dec;
    return true;
#else
    (void)sample_rate;
    return true;
#endif
}

int OpusAudioDecoder::decode(const uint8_t* pkt, size_t pkt_len, int16_t* out_pcm, size_t max_samples) {
#if defined(ESP_PLATFORM)
    if (!state_ || !out_pcm) return -1;
    OpusDecoder* dec = static_cast<OpusDecoder*>(state_);
    // If pkt is nullptr or pkt_len == 0, opus_decode invokes PLC (Packet Loss Concealment)
    return opus_decode(dec, pkt, pkt_len, out_pcm, max_samples, 0);
#else
    (void)pkt; (void)pkt_len; (void)out_pcm; (void)max_samples;
    return 480;
#endif
}

void OpusAudioDecoder::reset() {
#if defined(ESP_PLATFORM)
    if (state_) {
        opus_decoder_destroy(static_cast<OpusDecoder*>(state_));
        state_ = nullptr;
    }
#endif
}
