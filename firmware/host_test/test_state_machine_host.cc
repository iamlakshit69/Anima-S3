#include "app/state_machine.h"
#include <cassert>
#include <cstdio>

int main() {
    printf("[HOST_TEST] Running test_state_machine_host...\n");

    StateMachine sm;
    assert(sm.transition_count() >= 20);

    // 1. Verify specific key transitions from Section 7.5 table
    const Transition* t;

    // Boot -> Wifi
    t = sm.find_transition(DeviceState::BOOT, EventType::CREDENTIALS_SAVED);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_WIFI);

    // Boot -> Provisioning
    t = sm.find_transition(DeviceState::BOOT, EventType::NO_CREDENTIALS);
    assert(t != nullptr && t->to == DeviceState::PROVISIONING);

    // Wifi -> Connecting Server
    t = sm.find_transition(DeviceState::CONNECTING_WIFI, EventType::WIFI_UP);
    assert(t != nullptr && t->to == DeviceState::CONNECTING_SERVER);

    // Server connected -> IDLE
    t = sm.find_transition(DeviceState::CONNECTING_SERVER, EventType::HELLO_ACK);
    assert(t != nullptr && t->to == DeviceState::IDLE);

    // IDLE -> LISTENING (on WAKE or PTT_DOWN)
    t = sm.find_transition(DeviceState::IDLE, EventType::WAKE);
    assert(t != nullptr && t->to == DeviceState::LISTENING);

    t = sm.find_transition(DeviceState::IDLE, EventType::PTT_DOWN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);

    // LISTENING -> THINKING (on LISTEN_STOP)
    t = sm.find_transition(DeviceState::LISTENING, EventType::LISTEN_STOP);
    assert(t != nullptr && t->to == DeviceState::THINKING);

    // THINKING -> SPEAKING (on TTS_START)
    t = sm.find_transition(DeviceState::THINKING, EventType::TTS_START);
    assert(t != nullptr && t->to == DeviceState::SPEAKING);

    // SPEAKING -> IDLE (on PLAYBACK_DONE)
    t = sm.find_transition(DeviceState::SPEAKING, EventType::PLAYBACK_DONE);
    assert(t != nullptr && t->to == DeviceState::IDLE);

    // Barge-in: SPEAKING + TAP_BARGE_IN -> LISTENING
    t = sm.find_transition(DeviceState::SPEAKING, EventType::TAP_BARGE_IN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);

    // Barge-in: THINKING + TAP_BARGE_IN -> LISTENING
    t = sm.find_transition(DeviceState::THINKING, EventType::TAP_BARGE_IN);
    assert(t != nullptr && t->to == DeviceState::LISTENING);

    // 2. Unhandled event rejection test
    // IDLE + TTS_STOP is invalid
    t = sm.find_transition(DeviceState::IDLE, EventType::TTS_STOP);
    assert(t == nullptr);

    // BOOT + WAKE is invalid
    t = sm.find_transition(DeviceState::BOOT, EventType::WAKE);
    assert(t == nullptr);

    printf("[HOST_TEST] test_state_machine_host passed!\n");
    return 0;
}
