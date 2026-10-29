/*
 * firmware/main/net/ws_client.cc — WebSocket client implementation.
 */

#include "net/ws_client.h"
#include "config.h"
#include <stdlib.h>
#include <string.h>

#if defined(ESP_PLATFORM)
#include "esp_websocket_client.h"
#include "esp_log.h"
static const char* TAG = "ws_client";
static esp_websocket_client_handle_t s_client = nullptr;
#endif

static bool s_connected = false;
static uint32_t s_backoff_step = 0;
static const uint32_t s_backoff_steps_s[] = {1, 2, 4, 8, 16, 30};
static constexpr size_t kMaxBackoffSteps = sizeof(s_backoff_steps_s) / sizeof(s_backoff_steps_s[0]);
static WsEventCallback s_callback = nullptr;

bool WsClient::init(const char* url, const char* token, const char* device_id, WsEventCallback cb) {
    s_callback = cb;
#if defined(ESP_PLATFORM)
    char auth_header[128];
    snprintf(auth_header, sizeof(auth_header), "Bearer %s", token);

    esp_websocket_client_config_t ws_cfg = {};
    ws_cfg.uri = url;
    ws_cfg.ping_interval_sec = CONFIG_WS_PING_INTERVAL_S;
    ws_cfg.network_timeout_ms = CONFIG_WS_TIMEOUT_S * 1000;
    ws_cfg.disable_auto_reconnect = true; // Use app-level backoff per Architecture section 7.7
    ws_cfg.buffer_size = 4096;

    s_client = esp_websocket_client_init(&ws_cfg);
    if (!s_client) {
        ESP_LOGE(TAG, "Failed to initialize WebSocket client");
        return false;
    }

    esp_websocket_client_append_header(s_client, "Authorization", auth_header);
    esp_websocket_client_append_header(s_client, "X-Device-Id", device_id);
    return true;
#else
    (void)url; (void)token; (void)device_id;
    return true;
#endif
}

bool WsClient::connect() {
#if defined(ESP_PLATFORM)
    if (!s_client) return false;
    return (esp_websocket_client_start(s_client) == ESP_OK);
#else
    s_connected = true;
    return true;
#endif
}

void WsClient::disconnect() {
#if defined(ESP_PLATFORM)
    if (s_client) {
        esp_websocket_client_stop(s_client);
    }
#endif
    s_connected = false;
}

bool WsClient::is_connected() {
    return s_connected;
}

bool WsClient::send_text(const char* json_str) {
    if (!json_str) return false;
#if defined(ESP_PLATFORM)
    if (!s_client || !s_connected) return false;
    int len = strlen(json_str);
    return (esp_websocket_client_send_text(s_client, json_str, len, portMAX_DELAY) == len);
#else
    return true;
#endif
}

bool WsClient::send_binary(const uint8_t* data, size_t len) {
    if (!data || len == 0) return false;
#if defined(ESP_PLATFORM)
    if (!s_client || !s_connected) return false;
    return (esp_websocket_client_send_bin(s_client, reinterpret_cast<const char*>(data), len, portMAX_DELAY) == static_cast<int>(len));
#else
    return true;
#endif
}

uint32_t WsClient::get_next_backoff_delay_ms() {
    uint32_t base_s = s_backoff_steps_s[s_backoff_step];
    if (s_backoff_step + 1 < kMaxBackoffSteps) {
        s_backoff_step++;
    }
    // Add up to 20% random jitter (per Architecture section 4.5 & Appendix A)
    uint32_t jitter_ms = (rand() % (base_s * 200)); // up to 20% of base
    return (base_s * 1000) + jitter_ms;
}

void WsClient::reset_backoff() {
    s_backoff_step = 0;
}

