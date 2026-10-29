/*
 * firmware/main/ui/led_ui.cc — Status LED blink and pulse patterns.
 */

#include "ui/ui.h"
#include "boards/board.h"

#if defined(ESP_PLATFORM)
#include "driver/gpio.h"
#endif

class LedUi : public Ui {
public:
    LedUi() : current_state_(DeviceState::BOOT), tick_accum_ms_(0), led_on_(false) {}

    void init() override {
        set_led(false);
    }

    void show_state(DeviceState state) override {
        if (current_state_ != state) {
            current_state_ = state;
            tick_accum_ms_ = 0;
            update_pattern_immediate();
        }
    }

    void show_text(const char* /*text*/) override {
        // Plain LED has no text capability; reserved for LCD (Phase 6)
    }

    void show_emotion(const char* /*emotion*/) override {
        // Reserved for LCD (Phase 6)
    }

    void notify(const char* /*message*/) override {
        // Flash 3 quick blinks
        for (int i = 0; i < 3; ++i) {
            set_led(true);
            set_led(false);
        }
    }

    void tick(uint32_t delta_ms) override {
        tick_accum_ms_ += delta_ms;

        switch (current_state_) {
            case DeviceState::IDLE:
                set_led(false);
                break;

            case DeviceState::LISTENING:
                // Solid ON while microphone is actively streaming
                set_led(true);
                break;

            case DeviceState::THINKING:
                // Slow blink (500ms period)
                set_led((tick_accum_ms_ / 250) % 2 == 0);
                break;

            case DeviceState::SPEAKING:
                // Fast pulse (200ms period)
                set_led((tick_accum_ms_ / 100) % 2 == 0);
                break;

            case DeviceState::CONNECTING_WIFI:
            case DeviceState::CONNECTING_SERVER:
                // Pulse 1s
                set_led((tick_accum_ms_ / 500) % 2 == 0);
                break;

            case DeviceState::PROVISIONING:
                // Double blink pattern: 100 on, 100 off, 100 on, 700 off
                {
                    uint32_t phase = tick_accum_ms_ % 1000;
                    bool on = (phase < 100) || (phase >= 200 && phase < 300);
                    set_led(on);
                }
                break;

            case DeviceState::FATAL:
                // Fast strobe
                set_led((tick_accum_ms_ / 50) % 2 == 0);
                break;

            default:
                break;
        }
    }

private:
    void update_pattern_immediate() {
        if (current_state_ == DeviceState::IDLE) {
            set_led(false);
        } else if (current_state_ == DeviceState::LISTENING) {
            set_led(true);
        }
    }

    void set_led(bool on) {
        led_on_ = on;
#if defined(ESP_PLATFORM)
        int pin = Board::get()->get_status_led_pin();
        gpio_set_level(static_cast<gpio_num_t>(pin), on ? 1 : 0);
#endif
    }

    DeviceState current_state_;
    uint32_t tick_accum_ms_;
    bool led_on_;
};

static LedUi s_led_ui;

Ui* Ui::get() {
    return &s_led_ui;
}

