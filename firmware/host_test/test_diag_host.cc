#include "sys/diag.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>

int main() {
    printf("[HOST_TEST] Running test_diag_host...\n");

    // 1. Valid audio test (500 samples of 400Hz sine wave)
    std::vector<int16_t> audio(500);
    for (size_t i = 0; i < 500; ++i) {
        audio[i] = static_cast<int16_t>(sin(i * 0.1) * 15000);
    }
    MicSelfTestResult res = Diagnostics::analyze_mic_samples(audio.data(), audio.size());
    assert(res.ok == true);
    assert(res.rms > 0.05f);
    assert(!res.is_clipping);
    assert(!res.is_silent);

    // 2. Dead mic / silence test
    std::vector<int16_t> silence(500, 0);
    res = Diagnostics::analyze_mic_samples(silence.data(), silence.size());
    assert(res.ok == false);
    assert(res.is_silent == true);

    // 3. Clipped mic test (exceeds 32700 threshold)
    std::vector<int16_t> clipped(500, 32767);
    res = Diagnostics::analyze_mic_samples(clipped.data(), clipped.size());
    assert(res.ok == false);
    assert(res.is_clipping == true);

    // 4. System memory stats
    SystemStats stats = Diagnostics::get_stats();
    assert(stats.free_heap_bytes > 0);
    assert(stats.free_psram_bytes > 0);

    printf("[HOST_TEST] test_diag_host passed!\n");
    return 0;
}
