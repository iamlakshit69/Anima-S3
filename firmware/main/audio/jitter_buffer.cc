/*
 * firmware/main/audio/jitter_buffer.cc — Jitter buffer implementation.
 */

#include "audio/jitter_buffer.h"
#include <string.h>

JitterBuffer::JitterBuffer() : underruns_(0), is_playing_(false) {}

size_t JitterBuffer::push(const int16_t* pcm, size_t count) {
    return ring_.push(pcm, count);
}

bool JitterBuffer::pop(int16_t* dst, size_t count) {
    if (!dst || count == 0) return false;

    if (ring_.available_read() >= count) {
        ring_.pop(dst, count);
        is_playing_ = true;
        return true;
    }

    // Underrun: not enough audio available
    memset(dst, 0, count * sizeof(int16_t));
    if (is_playing_) {
        underruns_++;
    }
    return false;
}

bool JitterBuffer::is_prebuffered() const {
    return ring_.available_read() >= CONFIG_PREBUFFER_SAMPLES;
}

size_t JitterBuffer::buffered_samples() const {
    return ring_.available_read();
}

uint32_t JitterBuffer::buffered_ms() const {
    return static_cast<uint32_t>(ring_.available_read() * 1000ULL / CONFIG_AUDIO_DN_RATE);
}

uint32_t JitterBuffer::get_underrun_count() const {
    return underruns_;
}

void JitterBuffer::reset_underruns() {
    underruns_ = 0;
}

void JitterBuffer::clear() {
    ring_.clear();
    is_playing_ = false;
}

bool JitterBuffer::empty() const {
    return ring_.empty();
}
