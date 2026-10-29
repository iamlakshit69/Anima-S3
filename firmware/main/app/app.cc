/*
 * firmware/main/app/app.cc — Application coordinator implementation.
 */

#include "app/app.h"
#include "audio/audio_io.h"
#include "audio/cues.h"
#include "boards/board.h"
#include "net/ws_client.h"
#include "ui/ui.h"
#include <stdio.h>

#if defined(ESP_PLATFORM)
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
static const char* TAG = "app";
static QueueHandle_t s_event_queue = nullptr;
#endif

App& App::instance() {
    static App s_instance;
    return s_instance;
}

App::App()
    : state_(DeviceState::BOOT),
      turn_(0),
      uplink_active_(false),
      tts_stopped_flag_(false) {}

void App::init() {
#if defined(ESP_PLATFORM)
    s_event_queue = xQueueCreate(20, sizeof(Event));
#endif
    encoder_.init(CONFIG_AUDIO_UP_RATE, 20000);
    decoder_.init(CONFIG_AUDIO_DN_RATE);
    Ui::get()->init();
    Ui::get()->show_state(state_);
}

void App::post_event(const Event& event) {
#if defined(ESP_PLATFORM)
    if (s_event_queue) {
        xQueueSend(s_event_queue, &event, 0);
    }
#endif
}

void App::start_turn(const char* reason) {
    turn_++;
    uplink_active_ = true;
    AudioIO::set_mic_muted(false);

    // Play wake chime before uplink starts
    Cues::play(CueType::WAKE);

    char json_buf[128];
    snprintf(json_buf, sizeof(json_buf),
             "{\"type\":\"listen.start\",\"turn\":%u,\"reason\":\"%s\"}",
             turn_, reason);
    WsClient::send_text(json_buf);
}

void App::barge_in() {
    // Silences playback within 200ms (Goal G2)
    AudioIO::zero_spk_dma();
    jitter_buffer_.clear();

    char flushed_msg[64];
    snprintf(flushed_msg, sizeof(flushed_msg),
             "{\"type\":\"playback\",\"turn\":%u,\"event\":\"flushed\"}", turn_);
    WsClient::send_text(flushed_msg);

    // Immediately start new turn
    start_turn("barge_in");
}

void App::finish_turn() {
    uplink_active_ = false;
    AudioIO::set_mic_muted(true);
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
            if (state_ == DeviceState::IDLE) {
                start_turn("button");
                state_ = DeviceState::LISTENING;
                Ui::get()->show_state(state_);
            }
        } else if (btn_ev == ButtonEvent::PTT_UP) {
            if (state_ == DeviceState::LISTENING) {
                char end_buf[64];
                snprintf(end_buf, sizeof(end_buf), "{\"type\":\"listen.end\",\"turn\":%u}", turn_);
                WsClient::send_text(end_buf);
            }
        } else if (btn_ev == ButtonEvent::TAP) {
            if (state_ == DeviceState::SPEAKING || state_ == DeviceState::THINKING) {
                barge_in();
                state_ = DeviceState::LISTENING;
                Ui::get()->show_state(state_);
            } else if (state_ == DeviceState::IDLE) {
                start_turn("wake_word");
                state_ = DeviceState::LISTENING;
                Ui::get()->show_state(state_);
            }
        }

        // Tick LED pattern
        Ui::get()->tick(20);
    }
#endif
}
