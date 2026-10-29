/*
 * firmware/main/sys/settings.h — Non-Volatile Storage (NVS) settings manager.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

struct DeviceSettings {
    char server_url[128];
    char device_token[65];
    char wifi_ssid[33];
    char wifi_pass[65];
    uint8_t volume;
    uint8_t brightness;
    bool wake_enabled;
};

class Settings {
public:
    static bool init();
    static bool load(DeviceSettings* out);
    static bool save(const DeviceSettings& in);
    static const DeviceSettings& get();
    static void set_volume(uint8_t vol);
    static void set_brightness(uint8_t br);

private:
    static DeviceSettings s_current;
};
