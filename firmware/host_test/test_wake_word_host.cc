#include "audio/wake_word.h"
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
    printf("[HOST_TEST] Running test_wake_word_host...\n");

    WakeWordDetector detector;

    // 1. Initial state
    assert(!detector.is_armed());
    assert(!detector.fetch_detected());

    // 2. Initialization
    bool ok = detector.init("model");
    assert(ok == true);
    assert(detector.is_armed() == true);
    assert(detector.get_model_name() != nullptr);

    // 3. Audio feeding
    std::vector<int16_t> audio_block(320, 100);
    detector.feed(audio_block.data(), audio_block.size());
    assert(!detector.fetch_detected());

    // 4. Disarm / Arm behavior
    detector.set_armed(false);
    assert(!detector.is_armed());
    // When disarmed, feed is ignored
    detector.feed(audio_block.data(), audio_block.size());
    assert(!detector.fetch_detected());

    detector.set_armed(true);
    assert(detector.is_armed());

    // 5. Reset
    detector.reset();
    assert(!detector.is_armed());

    printf("[HOST_TEST] test_wake_word_host passed!\n");
    return 0;
}
