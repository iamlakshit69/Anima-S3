/*
 * firmware/main/sys/buttons.cc — Button debouncer implementation.
 */

#include "sys/buttons.h"

static constexpr uint32_t kDebounceMs = 30;
static constexpr uint32_t kLongPressMs = 3000;

ButtonDebouncer::ButtonDebouncer()
    : boot_down_(false),
      boot_duration_ms_(0),
      boot_long_fired_(false),
      ptt_down_(false),
      ptt_duration_ms_(0) {}

ButtonEvent ButtonDebouncer::update(bool boot_pressed, bool ptt_pressed, uint32_t delta_ms) {
    ButtonEvent event = ButtonEvent::NONE;

    // 1. Process PTT button (immediate down / up with debounce)
    if (ptt_pressed) {
        ptt_duration_ms_ += delta_ms;
        if (!ptt_down_ && ptt_duration_ms_ >= kDebounceMs) {
            ptt_down_ = true;
            event = ButtonEvent::PTT_DOWN;
        }
    } else {
        if (ptt_down_) {
            ptt_down_ = false;
            ptt_duration_ms_ = 0;
            event = ButtonEvent::PTT_UP;
        } else {
            ptt_duration_ms_ = 0;
        }
    }

    if (event != ButtonEvent::NONE) {
        return event;
    }

    // 2. Process BOOT button (Tap vs Long Press)
    if (boot_pressed) {
        boot_duration_ms_ += delta_ms;
        if (!boot_down_ && boot_duration_ms_ >= kDebounceMs) {
            boot_down_ = true;
        }
        if (boot_down_ && !boot_long_fired_ && boot_duration_ms_ >= kLongPressMs) {
            boot_long_fired_ = true;
            return ButtonEvent::LONG_PRESS;
        }
    } else {
        if (boot_down_) {
            if (!boot_long_fired_ && boot_duration_ms_ >= kDebounceMs) {
                event = ButtonEvent::TAP;
            }
            boot_down_ = false;
            boot_duration_ms_ = 0;
            boot_long_fired_ = false;
        } else {
            boot_duration_ms_ = 0;
        }
    }

    return event;
}

void ButtonDebouncer::reset() {
    boot_down_ = false;
    boot_duration_ms_ = 0;
    boot_long_fired_ = false;
    ptt_down_ = false;
    ptt_duration_ms_ = 0;
}

