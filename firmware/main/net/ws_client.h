/*
 * firmware/main/net/ws_client.h — WebSocket client with backoff and frame dispatch.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

typedef void (*WsEventCallback)(int event_id, void* data, size_t len);

class WsClient {
public:
    static bool init(const char* url, const char* token, const char* device_id, WsEventCallback cb);
    static bool connect();
    static void disconnect();
    static bool is_connected();

    static bool send_text(const char* json_str);
    static bool send_binary(const uint8_t* data, size_t len);

    static uint32_t get_next_backoff_delay_ms();
    static void reset_backoff();

    // Authentication error handling (Phase 5 acceptance)
    static bool has_auth_error();
    static void set_auth_error(bool err);
    static bool should_retry();
};

