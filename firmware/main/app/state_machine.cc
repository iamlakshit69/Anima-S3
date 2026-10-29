/*
 * firmware/main/app/state_machine.cc — Transition table implementation.
 */

#include "app/state_machine.h"
#include <stddef.h>

// Action callbacks delegating to AppContext
static void act_start_wifi(AppContext& ctx, const Event&) {
    ctx.connect_wifi();
}

static void act_start_prov(AppContext& ctx, const Event&) {
    ctx.start_provisioning();
}

static void act_connect_server(AppContext& ctx, const Event&) {
    ctx.connect_server();
}

static void act_on_connected(AppContext& ctx, const Event&) {
    ctx.on_connected();
}

static void act_on_disconnect(AppContext& ctx, const Event&) {
    ctx.on_disconnected();
}

static void act_start_listening(AppContext& ctx, const Event& ev) {
    const char* reason = (ev.type == EventType::WAKE) ? "wake_word" : "button";
    ctx.start_turn(reason);
}

static void act_stop_uplink(AppContext& ctx, const Event&) {
    ctx.stop_uplink();
}

static void act_send_listen_end(AppContext& ctx, const Event&) {
    ctx.send_listen_end();
}

static void act_abort_turn(AppContext& ctx, const Event&) {
    ctx.abort_turn();
}

static void act_start_playback(AppContext& ctx, const Event&) {
    ctx.start_playback();
}

static void act_finish_playback(AppContext& ctx, const Event&) {
    ctx.finish_playback();
}

static void act_barge_in(AppContext& ctx, const Event&) {
    ctx.barge_in();
}

static void act_start_ota(AppContext& ctx, const Event&) {
    ctx.start_ota();
}

static void act_ota_done(AppContext& ctx, const Event&) {
    ctx.ota_done();
}

static const Transition kTransitions[] = {
    // 1. Boot & Provisioning
    { DeviceState::BOOT, EventType::CREDENTIALS_SAVED, DeviceState::CONNECTING_WIFI, act_start_wifi },
    { DeviceState::BOOT, EventType::NO_CREDENTIALS,    DeviceState::PROVISIONING,    act_start_prov },
    { DeviceState::PROVISIONING, EventType::CREDENTIALS_SAVED, DeviceState::CONNECTING_WIFI, act_start_wifi },

    // 2. Wi-Fi & WebSocket Connection
    { DeviceState::CONNECTING_WIFI, EventType::WIFI_UP, DeviceState::CONNECTING_SERVER, act_connect_server },
    { DeviceState::CONNECTING_WIFI, EventType::WIFI_TIMEOUT, DeviceState::PROVISIONING, act_start_prov },
    { DeviceState::CONNECTING_SERVER, EventType::HELLO_ACK, DeviceState::IDLE, act_on_connected },

    // Reconnection on drops
    { DeviceState::IDLE,       EventType::WS_DOWN, DeviceState::CONNECTING_SERVER, act_on_disconnect },
    { DeviceState::LISTENING,  EventType::WS_DOWN, DeviceState::CONNECTING_SERVER, act_on_disconnect },
    { DeviceState::THINKING,   EventType::WS_DOWN, DeviceState::CONNECTING_SERVER, act_on_disconnect },
    { DeviceState::SPEAKING,   EventType::WS_DOWN, DeviceState::CONNECTING_SERVER, act_on_disconnect },
    { DeviceState::IDLE,       EventType::WIFI_DOWN, DeviceState::CONNECTING_WIFI, act_on_disconnect },
    { DeviceState::LISTENING,  EventType::WIFI_DOWN, DeviceState::CONNECTING_WIFI, act_on_disconnect },
    { DeviceState::THINKING,   EventType::WIFI_DOWN, DeviceState::CONNECTING_WIFI, act_on_disconnect },
    { DeviceState::SPEAKING,   EventType::WIFI_DOWN, DeviceState::CONNECTING_WIFI, act_on_disconnect },

    // 3. Conversation Turn Cycle
    { DeviceState::IDLE, EventType::WAKE,     DeviceState::LISTENING, act_start_listening },
    { DeviceState::IDLE, EventType::PTT_DOWN, DeviceState::LISTENING, act_start_listening },
    { DeviceState::IDLE, EventType::TAP_BARGE_IN, DeviceState::LISTENING, act_start_listening },
    { DeviceState::LISTENING, EventType::LISTEN_STOP, DeviceState::THINKING, act_stop_uplink },
    { DeviceState::LISTENING, EventType::PTT_UP,      DeviceState::LISTENING, act_send_listen_end },
    { DeviceState::LISTENING, EventType::TIMEOUT_LISTENING, DeviceState::IDLE, act_abort_turn },

    { DeviceState::THINKING, EventType::TTS_START, DeviceState::SPEAKING, act_start_playback },
    { DeviceState::THINKING, EventType::TTS_STOP,  DeviceState::IDLE,     act_abort_turn },

    { DeviceState::SPEAKING, EventType::PLAYBACK_DONE, DeviceState::IDLE, act_finish_playback },

    // 4. Barge-In (Tap during THINKING or SPEAKING interrupts assistant)
    { DeviceState::SPEAKING, EventType::TAP_BARGE_IN, DeviceState::LISTENING, act_barge_in },
    { DeviceState::THINKING, EventType::TAP_BARGE_IN, DeviceState::LISTENING, act_barge_in },

    // 5. OTA
    { DeviceState::IDLE, EventType::OTA_ACCEPTED, DeviceState::UPDATING, act_start_ota },
    { DeviceState::UPDATING, EventType::OTA_SUCCESS, DeviceState::BOOT, act_ota_done },
    { DeviceState::UPDATING, EventType::OTA_FAILURE, DeviceState::IDLE, nullptr },
};

static constexpr size_t kTransitionCount = sizeof(kTransitions) / sizeof(kTransitions[0]);

StateMachine::StateMachine() {}

const Transition* StateMachine::find_transition(DeviceState from, EventType event) const {
    for (size_t i = 0; i < kTransitionCount; ++i) {
        if (kTransitions[i].from == from && kTransitions[i].event == event) {
            return &kTransitions[i];
        }
    }
    return nullptr;
}

size_t StateMachine::transition_count() const {
    return kTransitionCount;
}

const Transition* StateMachine::get_transitions() const {
    return kTransitions;
}
