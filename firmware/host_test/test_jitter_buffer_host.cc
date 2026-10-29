#include "audio/jitter_buffer.h"
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
    printf("[HOST_TEST] Running test_jitter_buffer_host...\n");

    JitterBuffer jb;
    assert(jb.empty());
    assert(jb.get_underrun_count() == 0);
    assert(!jb.is_prebuffered());

    // 1. Push samples below prebuffer threshold (CONFIG_PREBUFFER_SAMPLES = 4800)
    std::vector<int16_t> chunk(2400, 100);
    jb.push(chunk.data(), chunk.size());
    assert(!jb.is_prebuffered());
    assert(jb.buffered_samples() == 2400);
    assert(jb.buffered_ms() == 100);

    // 2. Reach prebuffer threshold (total 4800 samples = 200ms)
    jb.push(chunk.data(), chunk.size());
    assert(jb.is_prebuffered());
    assert(jb.buffered_samples() == 4800);
    assert(jb.buffered_ms() == 200);

    // 3. Pop audio frames (480 samples = 20ms at 24kHz)
    int16_t out[480];
    bool ok = jb.pop(out, 480);
    assert(ok == true);
    assert(out[0] == 100);
    assert(jb.get_underrun_count() == 0);

    // 4. Drain buffer completely
    while (jb.buffered_samples() >= 480) {
        jb.pop(out, 480);
    }

    // 5. Underrun: pop when buffer is empty -> must fill with silence (0) and count underrun
    out[0] = 999;
    ok = jb.pop(out, 480);
    assert(ok == false);
    assert(out[0] == 0);
    assert(jb.get_underrun_count() == 1);

    // 6. Reset underrun count
    jb.reset_underruns();
    assert(jb.get_underrun_count() == 0);

    // 7. Clear (barge-in flush)
    jb.push(chunk.data(), chunk.size());
    assert(!jb.empty());
    jb.clear();
    assert(jb.empty());

    printf("[HOST_TEST] test_jitter_buffer_host passed!\n");
    return 0;
}
