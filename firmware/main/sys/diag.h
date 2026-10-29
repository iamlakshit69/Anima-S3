/*
 * firmware/main/sys/diag.h — Diagnostics, memory tracking, and self-test mode (Section 9.4).
 */

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

struct SystemStats {
    uint32_t free_heap_bytes;
    uint32_t free_psram_bytes;
    uint32_t min_free_heap_bytes;
    uint32_t uptime_seconds;
};

struct MicSelfTestResult {
    bool ok;
    float rms;
    int16_t peak_amplitude;
    bool is_clipping;
    bool is_silent;
};

class Diagnostics {
public:
    static SystemStats get_stats();
    static MicSelfTestResult analyze_mic_samples(const int16_t* pcm, size_t count);
    static void log_memory_report();
};

