/*
 * firmware/main/audio/opus_enc.cc — Opus encoder implementation.
 */

#include "audio/opus_enc.h"

#if defined(ESP_PLATFORM)
#include "opus.h"
#include "esp_log.h"
static const char* TAG = "opus_enc";
#endif

OpusAudioEncoder::OpusAudioEncoder() : state_(nullptr) {}

OpusAudioEncoder::~OpusAudioEncoder() {
    reset();
}

bool OpusAudioEncoder::init(uint32_t sample_rate, uint32_t bitrate) {
#if defined(ESP_PLATFORM)
    reset();
    int err = 0;
    OpusEncoder* enc = opus_encoder_create(sample_rate, 1, OPUS_APPLICATION_VOIP, &err);
    if (err != OPUS_OK || !enc) {
        ESP_LOGE(TAG, "Failed to create Opus encoder: %d", err);
        return false;
    }
    opus_encoder_ctl(enc, OPUS_SET_BITRATE(bitrate));
    opus_encoder_ctl(enc, OPUS_SET_COMPLEXITY(3)); // Complexity 3 is ideal for ESP32-S3 CPU
    opus_encoder_ctl(enc, OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE));
    state_ = enc;
    return true;
#else
    (void)sample_rate; (void)bitrate;
    return true;
#endif
}

int OpusAudioEncoder::encode(const int16_t* pcm, size_t samples, uint8_t* out_pkt, size_t max_bytes) {
#if defined(ESP_PLATFORM)
    if (!state_ || !pcm || !out_pkt) return -1;
    OpusEncoder* enc = static_cast<OpusEncoder*>(state_);
    return opus_encode(enc, pcm, samples, out_pkt, max_bytes);
#else
    (void)pcm; (void)samples; (void)out_pkt; (void)max_bytes;
    return 20; // Stub size on host
#endif
}

void OpusAudioEncoder::reset() {
#if defined(ESP_PLATFORM)
    if (state_) {
        opus_encoder_destroy(static_cast<OpusEncoder*>(state_));
        state_ = nullptr;
    }
#endif
}

