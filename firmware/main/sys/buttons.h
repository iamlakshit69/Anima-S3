/*
 * firmware/main/sys/buttons.h — Debounced button inputs (PTT and BOOT/Tap).
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

enum class ButtonEvent {
    NONE,
    TAP,            // Short press & release on BOOT button (wake / barge-in)
    LONG_PRESS,     // Hold BOOT >3s (enter provisioning)
    PTT_DOWN,       // Push-To-Talk button pressed down
    PTT_UP          // Push-To-Talk button released
};

class ButtonDebouncer {
public:
    ButtonDebouncer();

    /**
     * @brief Updates debouncer with raw sampled logic states.
     * Active low inputs: pass true if button is physically pressed down.
     * @param boot_pressed True if BOOT button is down.
     * @param ptt_pressed True if PTT button is down.
     * @param delta_ms Elapsed time since last update (ms).
     * @return Generated event, or ButtonEvent::NONE.
     */
    ButtonEvent update(bool boot_pressed, bool ptt_pressed, uint32_t delta_ms);

    void reset();

private:
    bool boot_down_;
    uint32_t boot_duration_ms_;
    bool boot_long_fired_;

    bool ptt_down_;
    uint32_t ptt_duration_ms_;
};
