/*
 * firmware/main/audio/jitter_buffer.h — Playback jitter buffer with prebuffer threshold and underrun tracking.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "config.h"
#include "audio/ring_buffer.h"

class JitterBuffer {
public:
    // Capacity: 65536 samples (power of two, covers 1.5s = 36,000 samples of 24 kHz audio)
    static constexpr size_t kCapacity = 65536;

    JitterBuffer();

    /**
     * @brief Pushes decoded PCM samples into the playback buffer.
     * @return Number of samples written.
     */
    size_t push(const int16_t* pcm, size_t count);

    /**
     * @brief Pops `count` samples for I2S output.
     * If insufficient samples, fills with silence and increments underrun count.
     * @return True if played real audio, false if underrun occurred (silence filled).
     */
    bool pop(int16_t* dst, size_t count);

    /**
     * @brief Checks if playback can start based on PREBUFFER_MS threshold.
     */
    bool is_prebuffered() const;

    size_t buffered_samples() const;
    uint32_t buffered_ms() const;
    uint32_t get_underrun_count() const;
    void reset_underruns();
    void clear();
    bool empty() const;

private:
    SpscRingBuffer<int16_t, kCapacity> ring_;
    uint32_t underruns_;
    bool is_playing_;
};

