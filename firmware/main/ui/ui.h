/*
 * firmware/main/ui/ui.h — User interface abstraction (LED status and future LCD).
 */

#pragma once

#include <stdint.h>

enum class DeviceState {
    BOOT,
    PROVISIONING,
    CONNECTING_WIFI,
    CONNECTING_SERVER,
    IDLE,
    LISTENING,
    THINKING,
    SPEAKING,
    UPDATING,
    FATAL
};

class Ui {
public:
    virtual ~Ui() = default;

    virtual void init() = 0;
    virtual void show_state(DeviceState state) = 0;
    virtual void show_text(const char* text) = 0;
    virtual void show_emotion(const char* emotion) = 0;
    virtual void notify(const char* message) = 0;
    virtual void tick(uint32_t delta_ms) = 0;

    static Ui* get();
};
