#include "app/state_machine.h"
#include "app/app_context.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>

class MockAppContext : public AppContext {
public:
    std::vector<std::string> calls;

    void start_turn(const char* reason) override { calls.push_back(std::string("start_turn:") + reason); }
    void stop_uplink() override { calls.push_back("stop_uplink"); }
    void send_listen_end() override { calls.push_back("send_listen_end"); }
    void abort_turn() override { calls.push_back("abort_turn"); }
    void start_playback() override { calls.push_back("start_playback"); }
    void finish_playback() override { calls.push_back("finish_playback"); }
    void barge_in() override { calls.push_back("barge_in"); }
    void connect_wifi() override { calls.push_back("connect_wifi"); }
    void connect_server() override { calls.push_back("connect_server"); }
    void on_connected() override { calls.push_back("on_connected"); }
    void on_disconnected() override { calls.push_back("on_disconnected"); }
    void start_provisioning() override { calls.push_back("start_provisioning"); }
    void start_ota() override { calls.push_back("start_ota"); }
    void ota_done() override { calls.push_back("ota_done"); }
};

int main() {
    printf("[HOST_TEST] Running test_state_machine_host...\n");

    StateMachine sm;
    assert(sm.transition_count() >= 25);

    MockAppContext ctx;
    const Transition* t;

    // 1. Boot & Provisioning
    t = sm.find_transition(DeviceState::BOOT, EventType::CREDENTIALS_SAVED);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_WIFI);
    t->action(ctx, Event{EventType::CREDENTIALS_SAVED, 0, false});
    assert(ctx.calls.back() == "connect_wifi");

    t = sm.find_transition(DeviceState::BOOT, EventType::NO_CREDENTIALS);
    assert(t != nullptr && t->to == DeviceState::PROVISIONING);
    t->action(ctx, Event{EventType::NO_CREDENTIALS, 0, false});
    assert(ctx.calls.back() == "start_provisioning");

    // 2. Wi-Fi & WebSocket Connection
    t = sm.find_transition(DeviceState::CONNECTING_WIFI, EventType::WIFI_UP);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_SERVER);
    t->action(ctx, Event{EventType::WIFI_UP, 0, false});
    assert(ctx.calls.back() == "connect_server");

    t = sm.find_transition(DeviceState::CONNECTING_WIFI, EventType::WIFI_TIMEOUT);
    assert(t != nullptr && t->to == DeviceState::PROVISIONING);

    t = sm.find_transition(DeviceState::CONNECTING_SERVER, EventType::HELLO_ACK);
    assert(t != nullptr && t->to == DeviceState::IDLE);
    t->action(ctx, Event{EventType::HELLO_ACK, 0, false});
    assert(ctx.calls.back() == "on_connected");

    // Reconnection on drops
    t = sm.find_transition(DeviceState::LISTENING, EventType::WS_DOWN);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_SERVER);
    t->action(ctx, Event{EventType::WS_DOWN, 0, false});
    assert(ctx.calls.back() == "on_disconnected");

    t = sm.find_transition(DeviceState::SPEAKING, EventType::WIFI_DOWN);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_WIFI);

    // 3. Conversation Turn Cycle
    t = sm.find_transition(DeviceState::IDLE, EventType::WAKE);
    assert(t != nullptr && t->to == DeviceState::LISTENING);
    t->action(ctx, Event{EventType::WAKE, 0, false});
    assert(ctx.calls.back() == "start_turn:wake_word");

    t = sm.find_transition(DeviceState::IDLE, EventType::PTT_DOWN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);
    t->action(ctx, Event{EventType::PTT_DOWN, 0, false});
    assert(ctx.calls.back() == "start_turn:button");

    t = sm.find_transition(DeviceState::LISTENING, EventType::LISTEN_STOP);
    assert(t != nullptr && t->to == DeviceState::THINKING);
    t->action(ctx, Event{EventType::LISTEN_STOP, 1, true});
    assert(ctx.calls.back() == "stop_uplink");

    t = sm.find_transition(DeviceState::LISTENING, EventType::PTT_UP);
    assert(t != nullptr && t->to == DeviceState::LISTENING);
    t->action(ctx, Event{EventType::PTT_UP, 1, true});
    assert(ctx.calls.back() == "send_listen_end");

    t = sm.find_transition(DeviceState::LISTENING, EventType::TIMEOUT_LISTENING);
    assert(t != nullptr && t->to == DeviceState::IDLE);
    t->action(ctx, Event{EventType::TIMEOUT_LISTENING, 1, true});
    assert(ctx.calls.back() == "abort_turn");

    t = sm.find_transition(DeviceState::THINKING, EventType::TTS_START);
    assert(t != nullptr && t->to == DeviceState::SPEAKING);
    t->action(ctx, Event{EventType::TTS_START, 1, true});
    assert(ctx.calls.back() == "start_playback");

    t = sm.find_transition(DeviceState::THINKING, EventType::TTS_STOP);
    assert(t != nullptr && t->to == DeviceState::IDLE);
    t->action(ctx, Event{EventType::TTS_STOP, 1, true});
    assert(ctx.calls.back() == "abort_turn");

    t = sm.find_transition(DeviceState::SPEAKING, EventType::PLAYBACK_DONE);
    assert(t != nullptr && t->to == DeviceState::IDLE);
    t->action(ctx, Event{EventType::PLAYBACK_DONE, 1, true});
    assert(ctx.calls.back() == "finish_playback");

    // 4. Barge-in (tap during SPEAKING or THINKING)
    t = sm.find_transition(DeviceState::SPEAKING, EventType::TAP_BARGE_IN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);
    t->action(ctx, Event{EventType::TAP_BARGE_IN, 1, true});
    assert(ctx.calls.back() == "barge_in");

    t = sm.find_transition(DeviceState::THINKING, EventType::TAP_BARGE_IN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);
    t->action(ctx, Event{EventType::TAP_BARGE_IN, 1, true});
    assert(ctx.calls.back() == "barge_in");

    // 5. OTA
    t = sm.find_transition(DeviceState::IDLE, EventType::OTA_ACCEPTED);
    assert(t != nullptr && t->to == DeviceState::UPDATING);
    t->action(ctx, Event{EventType::OTA_ACCEPTED, 0, false});
    assert(ctx.calls.back() == "start_ota");

    t = sm.find_transition(DeviceState::UPDATING, EventType::OTA_SUCCESS);
    assert(t != nullptr && t->to == DeviceState::BOOT);
    t->action(ctx, Event{EventType::OTA_SUCCESS, 0, false});
    assert(ctx.calls.back() == "ota_done");

    // 6. Unhandled events
    assert(sm.find_transition(DeviceState::IDLE, EventType::TTS_STOP) == nullptr);
    assert(sm.find_transition(DeviceState::BOOT, EventType::WAKE) == nullptr);

    printf("[HOST_TEST] test_state_machine_host passed! Verified %zu transitions.\n", sm.transition_count());
    return 0;
}
