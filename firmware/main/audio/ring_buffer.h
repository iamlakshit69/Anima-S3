/*
 * firmware/main/audio/ring_buffer.h — Lock-free Single-Producer Single-Consumer (SPSC) Ring Buffer.
 * PSRAM or SRAM backed, zero dynamic allocation during push/pop operations.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <atomic>
#include <algorithm>

template <typename T, size_t Capacity>
class SpscRingBuffer {
public:
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be a power of two for lock-free mask wrapping");

    SpscRingBuffer() : read_idx_(0), write_idx_(0) {}

    /**
     * @brief Pushes samples into the ring buffer.
     * @return Number of samples actually pushed (up to count).
     */
    size_t push(const T* src, size_t count) {
        if (!src || count == 0) return 0;

        size_t r = read_idx_.load(std::memory_order_relaxed);
        size_t w = write_idx_.load(std::memory_order_relaxed);
        size_t free_space = Capacity - (w - r);
        size_t to_write = std::min(count, free_space);

        if (to_write == 0) return 0;

        size_t mask = Capacity - 1;
        size_t first_chunk = std::min(to_write, Capacity - (w & mask));
        memcpy(&buffer_[w & mask], src, first_chunk * sizeof(T));
        if (to_write > first_chunk) {
            memcpy(&buffer_[0], src + first_chunk, (to_write - first_chunk) * sizeof(T));
        }

        write_idx_.store(w + to_write, std::memory_order_release);
        return to_write;
    }

    /**
     * @brief Pops samples from the ring buffer into destination array.
     * @return Number of samples actually read.
     */
    size_t pop(T* dst, size_t count) {
        if (!dst || count == 0) return 0;

        size_t r = read_idx_.load(std::memory_order_relaxed);
        size_t w = write_idx_.load(std::memory_order_acquire);
        size_t available = w - r;
        size_t to_read = std::min(count, available);

        if (to_read == 0) return 0;

        size_t mask = Capacity - 1;
        size_t first_chunk = std::min(to_read, Capacity - (r & mask));
        memcpy(dst, &buffer_[r & mask], first_chunk * sizeof(T));
        if (to_read > first_chunk) {
            memcpy(dst + first_chunk, &buffer_[0], (to_read - first_chunk) * sizeof(T));
        }

        read_idx_.store(r + to_read, std::memory_order_release);
        return to_read;
    }

    /**
     * @brief Discards oldest samples, keeping at most `keep_samples` in the buffer.
     * Used for pre-roll management when wake word or PTT fires.
     */
    void discard_older_than(size_t keep_samples) {
        size_t w = write_idx_.load(std::memory_order_acquire);
        size_t r = read_idx_.load(std::memory_order_relaxed);
        size_t available = w - r;
        if (available > keep_samples) {
            size_t to_discard = available - keep_samples;
            read_idx_.store(r + to_discard, std::memory_order_release);
        }
    }

    size_t available_read() const {
        size_t r = read_idx_.load(std::memory_order_relaxed);
        size_t w = write_idx_.load(std::memory_order_acquire);
        return w - r;
    }

    size_t available_write() const {
        return Capacity - available_read();
    }

    void clear() {
        size_t w = write_idx_.load(std::memory_order_relaxed);
        read_idx_.store(w, std::memory_order_release);
    }

    bool empty() const {
        return available_read() == 0;
    }

private:
    T buffer_[Capacity];
    alignas(64) std::atomic<size_t> read_idx_;
    alignas(64) std::atomic<size_t> write_idx_;
};

