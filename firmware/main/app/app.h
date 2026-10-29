/*
 * firmware/main/app/app.h — Main application controller.
 */

#pragma once

#include "app/app_context.h"
#include "app/events.h"
#include "app/state_machine.h"
#include "audio/ring_buffer.h"
#include "audio/jitter_buffer.h"
#include "audio/opus_enc.h"
#include "audio/opus_dec.h"
#include "audio/wake_word.h"
#include "sys/buttons.h"

struct DownlinkPacket {
    uint32_t turn;
    uint16_t len;
    uint8_t data[256];
};

class App : public AppContext {
public:
    static App& instance();

    void init();
    void run();
    void post_event(const Event& event);

    // AppContext overrides
    void start_turn(const char* reason) override;
    void stop_uplink() override;
    void send_listen_end() override;
    void abort_turn() override;
    void start_playback() override;
    void finish_playback() override;
    void barge_in() override;
    void connect_wifi() override;
    void connect_server() override;
    void on_connected() override;
    void on_disconnected() override;
    void start_provisioning() override;
    void start_ota() override;
    void ota_done() override;

    // Turn and state accessors
    uint32_t current_turn() const { return turn_; }
    DeviceState current_state() const { return state_; }
    bool is_uplink_active() const { return uplink_active_; }
    bool is_playing() const { return playing_; }
    void set_playing(bool p) { playing_ = p; }
    bool is_tts_stopped() const { return tts_stopped_flag_; }
    void set_tts_stopped(bool stopped) { tts_stopped_flag_ = stopped; }

    WakeWordDetector& wake_word() { return wake_word_; }
    JitterBuffer& jitter_buffer() { return jitter_buffer_; }
    OpusAudioEncoder& encoder() { return encoder_; }
    OpusAudioDecoder& decoder() { return decoder_; }

    // Audio stream buffers
    bool push_mic_audio(const int16_t* samples, size_t count);
    bool pop_mic_audio(int16_t* samples, size_t count, uint32_t timeout_ms = 0);
    bool push_playback_audio(const int16_t* samples, size_t count);
    bool pop_playback_audio(int16_t* samples, size_t count);
    bool is_jitter_buffer_empty() const;

    // Downlink packet handling
    bool enqueue_downlink_packet(const DownlinkPacket& pkt);
    bool pop_downlink_packet(DownlinkPacket* pkt, uint32_t timeout_ms = 0);

private:
    App();

    DeviceState state_;
    uint32_t turn_;
    StateMachine state_machine_;
    ButtonDebouncer debouncer_;

    RingBuffer<int16_t, 32000> mic_ring_;  // ~2s of 16 kHz audio
    JitterBuffer jitter_buffer_;           // ~1.5s of 24 kHz audio
    OpusAudioEncoder encoder_;
    OpusAudioDecoder decoder_;
    WakeWordDetector wake_word_;

    bool uplink_active_;
    bool playing_;
    bool tts_stopped_flag_;
    uint32_t listen_start_time_ms_;
};
