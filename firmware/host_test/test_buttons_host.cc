#include "sys/buttons.h"
#include <cassert>
#include <cstdio>

int main() {
    printf("[HOST_TEST] Running test_buttons_host...\n");

    ButtonDebouncer deb;

    // 1. Initial state
    assert(deb.update(false, false, 10) == ButtonEvent::NONE);

    // 2. PTT down and up
    // Less than debounce threshold (20ms < 30ms)
    assert(deb.update(false, true, 20) == ButtonEvent::NONE);
    // Crosses debounce threshold (20 + 15 = 35ms >= 30ms)
    assert(deb.update(false, true, 15) == ButtonEvent::PTT_DOWN);
    // Holding PTT generates no further event
    assert(deb.update(false, true, 100) == ButtonEvent::NONE);
    // Releasing PTT generates PTT_UP
    assert(deb.update(false, false, 10) == ButtonEvent::PTT_UP);
    assert(deb.update(false, false, 10) == ButtonEvent::NONE);

    // 3. BOOT short tap (wake / barge-in)
    // Press down for 100ms
    assert(deb.update(true, false, 50) == ButtonEvent::NONE);
    assert(deb.update(true, false, 50) == ButtonEvent::NONE);
    // Release generates TAP
    assert(deb.update(false, false, 10) == ButtonEvent::TAP);
    assert(deb.update(false, false, 10) == ButtonEvent::NONE);

    // 4. BOOT long press (> 3000ms, enter provisioning)
    deb.reset();
    assert(deb.update(true, false, 2000) == ButtonEvent::NONE);
    // Crosses 3000ms
    assert(deb.update(true, false, 1100) == ButtonEvent::LONG_PRESS);
    // Further hold generates nothing
    assert(deb.update(true, false, 500) == ButtonEvent::NONE);
    // Releasing after long press does NOT generate a TAP
    assert(deb.update(false, false, 50) == ButtonEvent::NONE);

    printf("[HOST_TEST] test_buttons_host passed!\n");
    return 0;
}
