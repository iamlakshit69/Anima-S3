/*
 * firmware/main/app/events.h — Event data structures for the firmware event loop.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "ui/ui.h"

enum class EventType {
    NONE = 0,
    BOOT_DONE,
    CREDENTIALS_SAVED,
    NO_CREDENTIALS,
    WIFI_UP,
    WIFI_DOWN,
    WIFI_TIMEOUT,
    HELLO_ACK,
    WS_DOWN,
    WAKE,
    PTT_DOWN,
    PTT_UP,
    TAP_BARGE_IN,
    LISTEN_STOP,
    TTS_START,
    TTS_STOP,
    PLAYBACK_DONE,
    TIMEOUT_LISTENING,
    OTA_ACCEPTED,
    OTA_SUCCESS,
    OTA_FAILURE
};

struct Event {
    EventType type;
    uint32_t turn;
    bool has_turn;
    int payload_int;
    void* payload_ptr;
};
