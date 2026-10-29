/*
 * firmware/main/boards/breadboard_s3/board.cc — Implementation for ESP32-S3 N16R8 breadboard.
 */

#include "boards/board.h"
#include "boards/breadboard_s3/pins.h"

#if defined(ESP_PLATFORM)
#include "driver/gpio.h"
#endif

class BreadboardS3 : public Board {
public:
    void init_gpio() override {
#if defined(ESP_PLATFORM)
        // Configure BOOT and PTT buttons as inputs with internal pull-up
        gpio_config_t btn_cfg = {
            .pin_bit_mask = (1ULL << PIN_BUTTON_BOOT) | (1ULL << PIN_BUTTON_PTT),
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_ENABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&btn_cfg);

        // Configure Status LED as output (default off)
        gpio_config_t led_cfg = {
            .pin_bit_mask = (1ULL << PIN_STATUS_LED),
            .mode = GPIO_MODE_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&led_cfg);
        gpio_set_level(static_cast<gpio_num_t>(PIN_STATUS_LED), 0);

        // Configure Lamp relay output (default OFF, Rule R12)
        gpio_config_t relay_cfg = {
            .pin_bit_mask = (1ULL << PIN_RELAY_LAMP),
            .mode = GPIO_MODE_OUTPUT,
            .pull_up_en = GPIO_PULLUP_DISABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&relay_cfg);
        gpio_set_level(static_cast<gpio_num_t>(PIN_RELAY_LAMP), 0);
#endif
    }

    BoardI2sPins get_mic_pins() const override {
        return {PIN_I2S_MIC_WS, PIN_I2S_MIC_SCK, PIN_I2S_MIC_SD};
    }

    BoardI2sPins get_spk_pins() const override {
        return {PIN_I2S_SPK_LRC, PIN_I2S_SPK_BCLK, PIN_I2S_SPK_DIN};
    }

    int get_status_led_pin() const override {
        return PIN_STATUS_LED;
    }

    int get_ptt_button_pin() const override {
        return PIN_BUTTON_PTT;
    }

    int get_boot_button_pin() const override {
        return PIN_BUTTON_BOOT;
    }

    void set_lamp_relay(bool active) override {
#if defined(ESP_PLATFORM)
        gpio_set_level(static_cast<gpio_num_t>(PIN_RELAY_LAMP), active ? 1 : 0);
#endif
    }
};

static BreadboardS3 s_board_instance;

Board* Board::get() {
    return &s_board_instance;
}
