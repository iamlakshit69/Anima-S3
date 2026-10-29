/*
 * firmware/host_test/test_soak_host.cc — State machine soak test (Phase 7).
 *
 * Verifies:
 *   - 100 consecutive turns cycling through IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE
 *   - 50 barge-in cycles during SPEAKING
 *   - Deterministic transitions, zero state corruption
 *   - Host-side stability check under continuous load
 */

#include "app/state_machine.h"
#include "app/app_context.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>

class SoakMockAppContext : public AppContext {
public:
    uint32_t turns_started = 0;
    uint32_t turns_aborted = 0;
    uint32_t playbacks_started = 0;
    uint32_t playbacks_finished = 0;
    uint32_t barge_ins = 0;

    void start_turn(const char* /*reason*/) override { turns_started++; }
    void stop_uplink() override {}
    void send_listen_end() override {}
    void abort_turn() override { turns_aborted++; }
    void start_playback() override { playbacks_started++; }
    void finish_playback() override { playbacks_finished++; }
    void barge_in() override { barge_ins++; }
    void connect_wifi() override {}
    void connect_server() override {}
    void on_connected() override {}
    void on_disconnected() override {}
    void start_provisioning() override {}
    void start_ota() override {}
    void ota_done() override {}
};

static void test_normal_dialogue_soak() {
    StateMachine sm;
    SoakMockAppContext ctx;
    DeviceState state = DeviceState::IDLE;

    const int NUM_CYCLES = 100;
    for (int i = 0; i < NUM_CYCLES; ++i) {
        // 1. Wake word -> LISTENING
        const Transition* t = sm.find_transition(state, EventType::WAKE);
        assert(t != nullptr && t->to == DeviceState::LISTENING);
        t->action(ctx, Event{EventType::WAKE, 0, false});
        state = t->to;

        // 2. Server endpoint -> THINKING
        t = sm.find_transition(state, EventType::LISTEN_STOP);
        assert(t != nullptr && t->to == DeviceState::THINKING);
        t->action(ctx, Event{EventType::LISTEN_STOP, 0, false});
        state = t->to;

        // 3. TTS start -> SPEAKING
        t = sm.find_transition(state, EventType::TTS_START);
        assert(t != nullptr && t->to == DeviceState::SPEAKING);
        t->action(ctx, Event{EventType::TTS_START, 0, false});
        state = t->to;

        // 4. Playback done -> IDLE
        t = sm.find_transition(state, EventType::PLAYBACK_DONE);
        assert(t != nullptr && t->to == DeviceState::IDLE);
        t->action(ctx, Event{EventType::PLAYBACK_DONE, 0, false});
        state = t->to;
    }

    assert(state == DeviceState::IDLE);
    assert(ctx.turns_started == NUM_CYCLES);
    assert(ctx.playbacks_started == NUM_CYCLES);
    assert(ctx.playbacks_finished == NUM_CYCLES);
}

static void test_barge_in_soak() {
    StateMachine sm;
    SoakMockAppContext ctx;
    DeviceState state = DeviceState::IDLE;

    const int NUM_CYCLES = 50;
    for (int i = 0; i < NUM_CYCLES; ++i) {
        // IDLE -> LISTENING -> THINKING -> SPEAKING
        const Transition* t = sm.find_transition(state, EventType::PTT_DOWN);
        assert(t != nullptr && t->to == DeviceState::LISTENING);
        t->action(ctx, Event{EventType::PTT_DOWN, 0, false});
        state = t->to;

        t = sm.find_transition(state, EventType::LISTEN_STOP);
        assert(t != nullptr && t->to == DeviceState::THINKING);
        t->action(ctx, Event{EventType::LISTEN_STOP, 0, false});
        state = t->to;

        t = sm.find_transition(state, EventType::TTS_START);
        assert(t != nullptr && t->to == DeviceState::SPEAKING);
        t->action(ctx, Event{EventType::TTS_START, 0, false});
        state = t->to;

        // Barge-in during SPEAKING -> LISTENING
        t = sm.find_transition(state, EventType::TAP_BARGE_IN);
        assert(t != nullptr && t->to == DeviceState::LISTENING);
        t->action(ctx, Event{EventType::TAP_BARGE_IN, 0, false});
        state = t->to;

        // Abort to IDLE
        t = sm.find_transition(state, EventType::TIMEOUT_LISTENING);
        assert(t != nullptr && t->to == DeviceState::IDLE);
        t->action(ctx, Event{EventType::TIMEOUT_LISTENING, 0, false});
        state = t->to;
    }

    assert(state == DeviceState::IDLE);
    assert(ctx.barge_ins == NUM_CYCLES);
}

int main() {
    printf("[HOST_TEST] Running test_soak_host (100 dialogue cycles, 50 barge-in cycles)...\n");
    test_normal_dialogue_soak();
    test_barge_in_soak();
    printf("[HOST_TEST] test_soak_host PASSED.\n");
    return 0;
}
