/*
 * firmware/main/sys/diag.cc — Diagnostics and self-test analysis implementation.
 */

#include "sys/diag.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(ESP_PLATFORM)
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#endif

SystemStats Diagnostics::get_stats() {
    SystemStats stats = {0, 0, 0, 0};
#if defined(ESP_PLATFORM)
    stats.free_heap_bytes = esp_get_free_heap_size();
    stats.min_free_heap_bytes = esp_get_minimum_free_heap_size();
    stats.free_psram_bytes = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    stats.uptime_seconds = static_cast<uint32_t>(esp_timer_get_time() / 1000000ULL);
#else
    stats.free_heap_bytes = 1024 * 1024;
    stats.free_psram_bytes = 8 * 1024 * 1024;
    stats.min_free_heap_bytes = 512 * 1024;
    stats.uptime_seconds = 100;
#endif
    return stats;
}

MicSelfTestResult Diagnostics::analyze_mic_samples(const int16_t* pcm, size_t count) {
    MicSelfTestResult res = {true, 0.0f, 0, false, false};
    if (!pcm || count == 0) {
        res.ok = false;
        res.is_silent = true;
        return res;
    }

    double sum_sq = 0.0;
    int16_t max_val = 0;

    for (size_t i = 0; i < count; ++i) {
        int16_t sample = pcm[i];
        int16_t abs_sample = abs(sample);
        if (abs_sample > max_val) {
            max_val = abs_sample;
        }
        double norm = static_cast<double>(sample) / 32768.0;
        sum_sq += norm * norm;
    }

    res.peak_amplitude = max_val;
    res.rms = static_cast<float>(sqrt(sum_sq / static_cast<double>(count)));

    // Clipping check: peak amplitude >= 32700 (near 16-bit max)
    if (max_val >= 32700) {
        res.is_clipping = true;
        res.ok = false;
    }

    // Dead mic check: RMS < 0.0005 over sample window
    if (res.rms < 0.0005f) {
        res.is_silent = true;
        res.ok = false;
    }

    return res;
}

void Diagnostics::log_memory_report() {
    SystemStats s = get_stats();
    printf("[DIAG] Free Heap: %u bytes (Min: %u) | Free PSRAM: %u bytes | Uptime: %u s\n",
           s.free_heap_bytes, s.min_free_heap_bytes, s.free_psram_bytes, s.uptime_seconds);
}
