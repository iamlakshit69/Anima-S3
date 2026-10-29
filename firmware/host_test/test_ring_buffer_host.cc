#include "audio/ring_buffer.h"
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
    printf("[HOST_TEST] Running test_ring_buffer_host...\n");

    SpscRingBuffer<int16_t, 1024> rb;
    assert(rb.empty());
    assert(rb.available_read() == 0);
    assert(rb.available_write() == 1024);

    // 1. Basic push and pop
    int16_t src[512];
    for (int i = 0; i < 512; ++i) src[i] = static_cast<int16_t>(i);

    size_t pushed = rb.push(src, 512);
    assert(pushed == 512);
    assert(rb.available_read() == 512);
    assert(rb.available_write() == 512);
    assert(!rb.empty());

    int16_t dst[512];
    size_t popped = rb.pop(dst, 512);
    assert(popped == 512);
    assert(rb.empty());
    for (int i = 0; i < 512; ++i) {
        assert(dst[i] == static_cast<int16_t>(i));
    }

    // 2. Wraparound test
    // Fill 800, pop 800 (moves write and read pointers forward)
    rb.push(src, 512);
    rb.pop(dst, 512);

    // Now push 800 across the 1024 boundary
    int16_t large[800];
    for (int i = 0; i < 800; ++i) large[i] = static_cast<int16_t>(i * 2);
    pushed = rb.push(large, 800);
    assert(pushed == 800);
    assert(rb.available_read() == 800);

    int16_t large_out[800];
    popped = rb.pop(large_out, 800);
    assert(popped == 800);
    for (int i = 0; i < 800; ++i) {
        assert(large_out[i] == static_cast<int16_t>(i * 2));
    }

    // 3. Overflow test
    int16_t full_test[1024];
    pushed = rb.push(full_test, 1024);
    assert(pushed == 1024);
    assert(rb.available_write() == 0);

    // Pushing more when full should return 0
    size_t extra = rb.push(src, 10);
    assert(extra == 0);

    // 4. discard_older_than test (pre-roll management)
    // Buffer has 1024 samples. Discard older than 200 samples.
    rb.discard_older_than(200);
    assert(rb.available_read() == 200);

    // 5. Clear
    rb.clear();
    assert(rb.empty());

    printf("[HOST_TEST] test_ring_buffer_host passed!\n");
    return 0;
}

