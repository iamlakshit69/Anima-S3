/*
 * firmware/main/boards/board.h — Hardware board abstraction interface.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

struct BoardI2sPins {
    int ws;
    int bclk;
    int data;
};

class Board {
public:
    virtual ~Board() = default;

    virtual void init_gpio() = 0;
    virtual BoardI2sPins get_mic_pins() const = 0;
    virtual BoardI2sPins get_spk_pins() const = 0;
    virtual int get_status_led_pin() const = 0;
    virtual int get_ptt_button_pin() const = 0;
    virtual int get_boot_button_pin() const = 0;
    virtual void set_lamp_relay(bool active) = 0;

    static Board* get();
};

