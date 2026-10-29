/*
 * firmware/main/sys/settings.cc — NVS settings implementation.
 */

#include "sys/settings.h"
#include <string.h>

#if defined(ESP_PLATFORM)
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
static const char* TAG = "settings";
#endif

DeviceSettings Settings::s_current = {
    .server_url = "ws://192.168.1.100:8765/v1/device",
    .device_token = "test-token-32-chars-long-fake-dev",
    .wifi_ssid = "MyHomeWiFi",
    .wifi_pass = "",
    .volume = 70,
    .brightness = 80,
    .wake_enabled = true
};

bool Settings::init() {
#if defined(ESP_PLATFORM)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    return (ret == ESP_OK);
#else
    return true;
#endif
}

bool Settings::load(DeviceSettings* out) {
    if (!out) return false;
    *out = s_current;
    return true;
}

bool Settings::save(const DeviceSettings& in) {
    s_current = in;
    return true;
}

const DeviceSettings& Settings::get() {
    return s_current;
}

void Settings::set_volume(uint8_t vol) {
    s_current.volume = (vol > 100) ? 100 : vol;
}

void Settings::set_brightness(uint8_t br) {
    s_current.brightness = (br > 100) ? 100 : br;
}
