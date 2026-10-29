/*
 * firmware/main/app/app.h — Main firmware application coordinator.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "app/events.h"
#include "app/state_machine.h"
#include "audio/jitter_buffer.h"
#include "audio/ring_buffer.h"
#include "audio/opus_enc.h"
#include "audio/opus_dec.h"
#include "sys/buttons.h"

class App : public AppContext {
public:
    static App& instance();

    void init();
    void run();

    void post_event(const Event& event);
    DeviceState get_state() const { return state_; }
    uint32_t get_turn() const { return turn_; }

    void start_turn(const char* reason);
    void finish_turn();
    void barge_in();

private:
    App();

    DeviceState state_;
    uint32_t turn_;
    StateMachine state_machine_;
    ButtonDebouncer debouncer_;
    JitterBuffer jitter_buffer_;
    OpusAudioEncoder encoder_;
    OpusAudioDecoder decoder_;

    bool uplink_active_;
    bool tts_stopped_flag_;
};
