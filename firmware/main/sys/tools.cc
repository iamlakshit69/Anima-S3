/*
 * firmware/main/sys/tools.cc — Device-side tool registry and execution engine.
 */

#include "sys/tools.h"
#include "sys/settings.h"
#include "boards/breadboard_s3/pins.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#if defined(ESP_PLATFORM)
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_log.h"
static const char* TAG = "tools";
#endif

// Hardcoded forbidden capabilities per Rule R7
static const char* kForbiddenTools[] = {
    "reboot",
    "upgrade_firmware",
    "wifi_",
    "factory_reset",
    "set_token"
};
static constexpr size_t kForbiddenCount = sizeof(kForbiddenTools) / sizeof(kForbiddenTools[0]);

// Simple argument extractors
static bool extract_int(const char* json, const char* key, int* out_val) {
    if (!json || !key || !out_val) return false;
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char* pos = strstr(json, needle);
    if (!pos) return false;
    pos += strlen(needle);
    while (*pos == ' ' || *pos == ':' || *pos == '\t') pos++;
    char* endptr = nullptr;
    long val = strtol(pos, &endptr, 10);
    if (endptr == pos) return false;
    *out_val = static_cast<int>(val);
    return true;
}

static bool extract_bool(const char* json, const char* key, bool* out_val) {
    if (!json || !key || !out_val) return false;
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char* pos = strstr(json, needle);
    if (!pos) return false;
    pos += strlen(needle);
    while (*pos == ' ' || *pos == ':' || *pos == '\t') pos++;
    if (strncmp(pos, "true", 4) == 0) {
        *out_val = true;
        return true;
    } else if (strncmp(pos, "false", 5) == 0) {
        *out_val = false;
        return true;
    }
    return false;
}

// Lamp rate limiting: max 10 toggles per minute (Architecture Section 7.8)
static uint32_t s_lamp_toggle_count = 0;
static uint32_t s_lamp_window_start_ms = 0;

static uint32_t get_time_ms() {
#if defined(ESP_PLATFORM)
    return static_cast<uint32_t>(esp_timer_get_time() / 1000);
#else
    return 0;
#endif
}

ToolResult ToolDispatcher::tool_set_volume(const char* args_json) {
    int level = -1;
    if (!extract_int(args_json, "level", &level)) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_BAD_ARGS", sizeof(r.error) - 1);
        return r;
    }
    // Clamp level to [0, 100] (Rule R8)
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    Settings::set_volume(static_cast<uint8_t>(level));

    ToolResult r = {};
    r.ok = true;
    snprintf(r.payload, sizeof(r.payload), "{\"status\":\"ok\",\"volume\":%d}", level);
    return r;
}

ToolResult ToolDispatcher::tool_set_brightness(const char* args_json) {
    int level = -1;
    if (!extract_int(args_json, "level", &level)) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_BAD_ARGS", sizeof(r.error) - 1);
        return r;
    }
    if (level < 0) level = 0;
    if (level > 100) level = 100;
    Settings::set_brightness(static_cast<uint8_t>(level));

    ToolResult r = {};
    r.ok = true;
    snprintf(r.payload, sizeof(r.payload), "{\"status\":\"ok\",\"brightness\":%d}", level);
    return r;
}

ToolResult ToolDispatcher::tool_lamp_set(const char* args_json) {
    bool on = false;
    if (!extract_bool(args_json, "on", &on)) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_BAD_ARGS", sizeof(r.error) - 1);
        return r;
    }

    // Rate limit check: max 10 changes per minute
    uint32_t now = get_time_ms();
    if (now - s_lamp_window_start_ms >= 60000) {
        s_lamp_window_start_ms = now;
        s_lamp_toggle_count = 0;
    }
    if (s_lamp_toggle_count >= 10) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_DENIED", sizeof(r.error) - 1);
        return r;
    }
    s_lamp_toggle_count++;

#if defined(ESP_PLATFORM)
    gpio_set_level(static_cast<gpio_num_t>(PIN_RELAY_LAMP), on ? 1 : 0);
#endif

    ToolResult r = {};
    r.ok = true;
    snprintf(r.payload, sizeof(r.payload), "{\"status\":\"ok\",\"on\":%s}", on ? "true" : "false");
    return r;
}

ToolResult ToolDispatcher::tool_get_status(const char* /*args_json*/) {
    ToolResult r = {};
    r.ok = true;
    uint8_t vol = Settings::get().volume;
    snprintf(r.payload, sizeof(r.payload),
             "{\"battery_pct\":100,\"volume\":%u,\"wifi_rssi\":-50}", vol);
    return r;
}

static const Tool kTools[] = {
    {
        "set_volume",
        "Set speaker volume 0-100",
        "{\"type\":\"object\",\"properties\":{\"level\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":100}},\"required\":[\"level\"]}",
        ToolRisk::SAFE,
        ToolDispatcher::tool_set_volume
    },
    {
        "set_brightness",
        "Set screen brightness 0-100",
        "{\"type\":\"object\",\"properties\":{\"level\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":100}},\"required\":[\"level\"]}",
        ToolRisk::SAFE,
        ToolDispatcher::tool_set_brightness
    },
    {
        "lamp_set",
        "Turn the lamp relay on or off",
        "{\"type\":\"object\",\"properties\":{\"on\":{\"type\":\"boolean\"}},\"required\":[\"on\"]}",
        ToolRisk::SAFE,
        ToolDispatcher::tool_lamp_set
    },
    {
        "get_status",
        "Battery, volume, wifi signal",
        "{\"type\":\"object\",\"properties\":{}}",
        ToolRisk::SAFE,
        ToolDispatcher::tool_get_status
    }
};

static constexpr size_t kToolCount = sizeof(kTools) / sizeof(kTools[0]);

void ToolDispatcher::init() {
#if defined(ESP_PLATFORM)
    // Rule R12: Relay output defaults to off (low) at boot
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << PIN_RELAY_LAMP);
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pull_down_en = GPIO_PULLDOWN_ENABLE;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    gpio_config(&io_conf);
    gpio_set_level(static_cast<gpio_num_t>(PIN_RELAY_LAMP), 0);
#endif
}

bool ToolDispatcher::is_forbidden(const char* tool_name) {
    if (!tool_name) return true;
    for (size_t i = 0; i < kForbiddenCount; ++i) {
        if (strstr(tool_name, kForbiddenTools[i]) != nullptr) {
            return true;
        }
    }
    return false;
}

const Tool* ToolDispatcher::find_tool(const char* tool_name) {
    if (!tool_name) return nullptr;
    // Strip "device." prefix if present
    const char* clean_name = tool_name;
    if (strncmp(clean_name, "device.", 7) == 0) {
        clean_name += 7;
    }
    for (size_t i = 0; i < kToolCount; ++i) {
        if (strcmp(kTools[i].name, clean_name) == 0) {
            return &kTools[i];
        }
    }
    return nullptr;
}

size_t ToolDispatcher::tool_count() {
    return kToolCount;
}

const Tool* ToolDispatcher::get_tools() {
    return kTools;
}

ToolResult ToolDispatcher::dispatch(const char* tool_name, const char* args_json) {
    // 1. Strict Rule R7 forbidden capability check
    if (is_forbidden(tool_name)) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_DENIED", sizeof(r.error) - 1);
        return r;
    }

    // 2. Allowlist lookup
    const Tool* tool = find_tool(tool_name);
    if (!tool || tool->risk != ToolRisk::SAFE) {
        ToolResult r = {};
        r.ok = false;
        strncpy(r.error, "E_TOOL_DENIED", sizeof(r.error) - 1);
        return r;
    }

    // 3. Execution
    return tool->fn(args_json);
}

