/*
 * firmware/main/app/app.cc — Application coordinator implementation.
 */

#include "app/app.h"
#include "audio/audio_io.h"
#include "audio/cues.h"
#include "boards/board.h"
#include "net/ws_client.h"
#include "net/protocol_gen.h"
#include "config.h"
#include "ui/ui.h"
#include <stdio.h>
#include <string.h>

#if defined(ESP_PLATFORM)
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_timer.h"
#include "esp_log.h"
static const char* TAG = "app";
static QueueHandle_t s_event_queue = nullptr;
static QueueHandle_t s_dec_queue = nullptr;

static uint32_t get_time_ms() {
    return static_cast<uint32_t>(esp_timer_get_time() / 1000);
}
#else
static uint32_t get_time_ms() {
    return 0;
}
#endif

// FreeRTOS Task definitions
#if defined(ESP_PLATFORM)
static void audio_in_task(void* arg) {
    App* app = static_cast<App*>(arg);
    int16_t block[CONFIG_AUDIO_IN_FRAME_SAMPLES]; // 320 samples (20 ms at 16 kHz)
    for (;;) {
        AudioIO::read_mic_mono16(block, CONFIG_AUDIO_IN_FRAME_SAMPLES);
        if (AudioIO::is_mic_muted()) {
            continue; // Keep draining DMA, discard
        }
        app->push_mic_audio(block, CONFIG_AUDIO_IN_FRAME_SAMPLES);
        if (app->wake_word().is_armed()) {
            app->wake_word().feed(block, CONFIG_AUDIO_IN_FRAME_SAMPLES);
        }
    }
}

static void afe_wake_task(void* arg) {
    App* app = static_cast<App*>(arg);
    for (;;) {
        if (app->wake_word().fetch_detected()) {
            app->post_event(Event{EventType::WAKE, 0, false});
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void audio_out_task(void* arg) {
    App* app = static_cast<App*>(arg);
    int16_t out[CONFIG_AUDIO_OUT_FRAME_SAMPLES]; // 480 samples (20 ms at 24 kHz)
    for (;;) {
        if (!app->is_playing()) {
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }
        if (app->pop_playback_audio(out, CONFIG_AUDIO_OUT_FRAME_SAMPLES)) {
            AudioIO::write_spk_mono16(out, CONFIG_AUDIO_OUT_FRAME_SAMPLES);
        } else {
            AudioIO::write_spk_silence(CONFIG_AUDIO_OUT_FRAME_SAMPLES);
        }
        if (app->is_tts_stopped() && app->is_jitter_buffer_empty()) {
            app->set_playing(false);
            app->post_event(Event{EventType::PLAYBACK_DONE, app->current_turn(), true});
        }
    }
}

static void opus_enc_task(void* arg) {
    App* app = static_cast<App*>(arg);
    int16_t pcm[CONFIG_AUDIO_IN_FRAME_SAMPLES];
    uint8_t pkt[256];
    uint16_t seq = 0;
    bool first = true;
    for (;;) {
        if (!app->is_uplink_active()) {
            seq = 0;
            first = true;
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }
        if (!app->pop_mic_audio(pcm, CONFIG_AUDIO_IN_FRAME_SAMPLES, 20)) {
            continue;
        }
        int n = app->encoder().encode(pcm, CONFIG_AUDIO_IN_FRAME_SAMPLES, pkt, sizeof(pkt));
        if (n > 0) {
            uint32_t t_ms = get_time_ms();
            uint8_t frame_buf[sizeof(AnimaFrameHeader) + 256];
            AnimaFrameHeader hdr;
            hdr.kind = ANIMA_KIND_UP;
            hdr.flags = first ? ANIMA_FLAG_FIRST : 0;
            hdr.seq = seq++;
            hdr.turn = app->current_turn();
            hdr.t_ms = t_ms;
            memcpy(frame_buf, &hdr, sizeof(hdr));
            memcpy(frame_buf + sizeof(hdr), pkt, n);
            WsClient::send_binary(frame_buf, sizeof(hdr) + n);
            first = false;
        }
    }
}

static void opus_dec_task(void* arg) {
    App* app = static_cast<App*>(arg);
    int16_t pcm[CONFIG_AUDIO_OUT_FRAME_SAMPLES];
    for (;;) {
        DownlinkPacket pkt;
        if (!app->pop_downlink_packet(&pkt, 50)) {
            continue;
        }
        if (pkt.turn != app->current_turn()) {
            // Rule T7: Drop stale downlink packet
            continue;
        }
        int decoded = app->decoder().decode(pkt.data, pkt.len, pcm, CONFIG_AUDIO_OUT_FRAME_SAMPLES);
        if (decoded > 0) {
            app->push_playback_audio(pcm, decoded);
            if (!app->is_playing() && app->jitter_buffer().buffered_ms() >= CONFIG_PREBUFFER_MS) {
                app->set_playing(true);
                char play_msg[64];
                snprintf(play_msg, sizeof(play_msg), "{\"type\":\"playback\",\"turn\":%u,\"event\":\"started\"}", app->current_turn());
                WsClient::send_text(play_msg);
            }
        }
    }
}
#endif

App& App::instance() {
    static App s_instance;
    return s_instance;
}

App::App()
    : state_(DeviceState::BOOT),
      turn_(0),
      uplink_active_(false),
      playing_(false),
      tts_stopped_flag_(false),
      listen_start_time_ms_(0) {}

void App::init() {
#if defined(ESP_PLATFORM)
    s_event_queue = xQueueCreate(20, sizeof(Event));
    s_dec_queue = xQueueCreate(100, sizeof(DownlinkPacket)); // 100 packets queue (Architecture 7.4)
#endif
    encoder_.init(CONFIG_AUDIO_UP_RATE, 20000);
    decoder_.init(CONFIG_AUDIO_DN_RATE);
    wake_word_.init("model");
    Ui::get()->init();
    Ui::get()->show_state(state_);

#if defined(ESP_PLATFORM)
    // Core 1: DSP and I2S tasks (Architecture 7.4)
    xTaskCreatePinnedToCore(audio_in_task, "audio_in", 4096, this, 9, nullptr, 1);
    xTaskCreatePinnedToCore(afe_wake_task, "afe_wake", 8192, this, 8, nullptr, 1);
    xTaskCreatePinnedToCore(audio_out_task, "audio_out", 4096, this, 9, nullptr, 1);

    // Core 0: Network and Opus codec tasks
    xTaskCreatePinnedToCore(opus_enc_task, "opus_enc", 24576, this, 5, nullptr, 0);
    xTaskCreatePinnedToCore(opus_dec_task, "opus_dec", 24576, this, 6, nullptr, 0);
#endif
}

void App::post_event(const Event& event) {
#if defined(ESP_PLATFORM)
    if (s_event_queue) {
        xQueueSend(s_event_queue, &event, 0);
    }
#else
    (void)event;
#endif
}

void App::start_turn(const char* reason) {
    turn_++;
    uplink_active_ = true;
    wake_word_.set_armed(false);
    AudioIO::set_mic_muted(false);
    listen_start_time_ms_ = get_time_ms();

    // Play wake chime before uplink starts
    Cues::play(CueType::WAKE);

    char json_buf[128];
    snprintf(json_buf, sizeof(json_buf),
             "{\"type\":\"listen.start\",\"turn\":%u,\"reason\":\"%s\"}",
             turn_, reason);
    WsClient::send_text(json_buf);
}

void App::stop_uplink() {
    uplink_active_ = false;
}

void App::send_listen_end() {
    char end_buf[64];
    snprintf(end_buf, sizeof(end_buf), "{\"type\":\"listen.end\",\"turn\":%u}", turn_);
    WsClient::send_text(end_buf);
}

void App::abort_turn() {
    char abort_buf[64];
    snprintf(abort_buf, sizeof(abort_buf), "{\"type\":\"abort\",\"turn\":%u}", turn_);
    WsClient::send_text(abort_buf);

    uplink_active_ = false;
    AudioIO::set_mic_muted(true);
    wake_word_.set_armed(true);
}

void App::start_playback() {
    AudioIO::set_mic_muted(true);
    playing_ = false;
    tts_stopped_flag_ = false;
}

void App::finish_playback() {
    playing_ = false;
#if defined(ESP_PLATFORM)
    vTaskDelay(pdMS_TO_TICKS(CONFIG_MIC_TAIL_MS)); // 300 ms room decay
#endif
    AudioIO::set_mic_muted(false);
    wake_word_.set_armed(true);
    tts_stopped_flag_ = false;

    char finished_buf[64];
    snprintf(finished_buf, sizeof(finished_buf),
             "{\"type\":\"playback\",\"turn\":%u,\"event\":\"finished\"}", turn_);
    WsClient::send_text(finished_buf);
}

void App::barge_in() {
    playing_ = false;
    AudioIO::zero_spk_dma();
    jitter_buffer_.clear();

    char flushed_msg[64];
    snprintf(flushed_msg, sizeof(flushed_msg),
             "{\"type\":\"playback\",\"turn\":%u,\"event\":\"flushed\"}", turn_);
    WsClient::send_text(flushed_msg);

    start_turn("barge_in");
}

void App::connect_wifi() {
    // Wi-Fi station connect
}

void App::connect_server() {
    WsClient::connect();
}

void App::on_connected() {
    wake_word_.set_armed(true);
    AudioIO::set_mic_muted(false);
}

void App::on_disconnected() {
    uplink_active_ = false;
    playing_ = false;
    AudioIO::zero_spk_dma();
    jitter_buffer_.clear();
    AudioIO::set_mic_muted(true);
    wake_word_.set_armed(false);
}

void App::start_provisioning() {
    Ui::get()->show_state(DeviceState::PROVISIONING);
}

void App::start_ota() {
    Ui::get()->show_state(DeviceState::UPDATING);
}

void App::ota_done() {
    // System reboot on OTA success
}

bool App::push_mic_audio(const int16_t* samples, size_t count) {
    return mic_ring_.push(samples, count);
}

bool App::pop_mic_audio(int16_t* samples, size_t count, uint32_t timeout_ms) {
    return mic_ring_.pop(samples, count, timeout_ms);
}

bool App::push_playback_audio(const int16_t* samples, size_t count) {
    return jitter_buffer_.push(samples, count);
}

bool App::pop_playback_audio(int16_t* samples, size_t count) {
    return jitter_buffer_.pop(samples, count);
}

bool App::is_jitter_buffer_empty() const {
    return jitter_buffer_.empty();
}

bool App::enqueue_downlink_packet(const DownlinkPacket& pkt) {
#if defined(ESP_PLATFORM)
    if (s_dec_queue) {
        return (xQueueSend(s_dec_queue, &pkt, 0) == pdTRUE);
    }
#else
    (void)pkt;
#endif
    return false;
}

bool App::pop_downlink_packet(DownlinkPacket* pkt, uint32_t timeout_ms) {
#if defined(ESP_PLATFORM)
    if (s_dec_queue) {
        return (xQueueReceive(s_dec_queue, pkt, pdMS_TO_TICKS(timeout_ms)) == pdTRUE);
    }
#else
    (void)pkt;
    (void)timeout_ms;
#endif
    return false;
}

void App::run() {
#if defined(ESP_PLATFORM)
    Event e;
    for (;;) {
        if (xQueueReceive(s_event_queue, &e, pdMS_TO_TICKS(20)) == pdTRUE) {
            // Rule T7: Drop stale turn events
            if (e.has_turn && e.turn < turn_) {
                continue;
            }

            const Transition* t = state_machine_.find_transition(state_, e.type);
            if (t) {
                if (t->action) {
                    t->action(*this, e);
                }
                state_ = t->to;
                Ui::get()->show_state(state_);
            }
        }

        // Poll button debouncer
        Board* board = Board::get();
        bool boot_pressed = (gpio_get_level(static_cast<gpio_num_t>(board->get_boot_button_pin())) == 0);
        bool ptt_pressed = (gpio_get_level(static_cast<gpio_num_t>(board->get_ptt_button_pin())) == 0);

        ButtonEvent btn_ev = debouncer_.update(boot_pressed, ptt_pressed, 20);
        if (btn_ev == ButtonEvent::PTT_DOWN) {
            post_event(Event{EventType::PTT_DOWN, 0, false});
        } else if (btn_ev == ButtonEvent::PTT_UP) {
            post_event(Event{EventType::PTT_UP, turn_, true});
        } else if (btn_ev == ButtonEvent::TAP) {
            if (state_ == DeviceState::SPEAKING || state_ == DeviceState::THINKING) {
                post_event(Event{EventType::TAP_BARGE_IN, turn_, true});
            } else if (state_ == DeviceState::IDLE) {
                post_event(Event{EventType::WAKE, 0, false});
            }
        }

        // Listening timeout watchdog (Architecture 7.5: 25s limit)
        if (state_ == DeviceState::LISTENING) {
            uint32_t now = get_time_ms();
            if (now - listen_start_time_ms_ >= (CONFIG_LISTENING_LIMIT_S * 1000)) {
                post_event(Event{EventType::TIMEOUT_LISTENING, turn_, true});
            }
        }

        // Tick UI animation pattern
        Ui::get()->tick(20);
    }
#endif
}
