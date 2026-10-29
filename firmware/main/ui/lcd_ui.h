/*
 * firmware/main/ui/lcd_ui.h — LCD display UI abstraction (Phase 6).
 *
 * Implements the Ui interface for a 128x160 ST7735/ST7789-compatible SPI
 * panel.  Compiled only when CONFIG_LCD_ENABLED is defined; the host tests
 * stub out the SPI calls so the class logic is still exercised.
 *
 * HARDWARE NOTICE (Rule R15): pin numbers come from docs/HARDWARE.md /
 * boards/breadboard_s3/pins.h. They are UNVERIFIED AI-generated defaults.
 * Do not flash until the actual wiring is confirmed and written to
 * docs/HARDWARE.md.
 *
 * Layout (Architecture §7.11):
 *   - Row 0–15   : status bar – state icon and label
 *   - Row 16–95  : emotion glyph centred
 *   - Row 96–159 : scrolling subtitle (stt / reply text)
 *
 * v1 uses text-only rendering via the ST7735 command layer; pixel fonts
 * are deferred to Phase 7 when actual hardware is confirmed.
 */

#pragma once

#include "ui/ui.h"

#include <cstdint>
#include <cstring>

// Maximum characters held in each text region (host-safe sizes)
static constexpr size_t LCD_STATUS_MAX  = 20;
static constexpr size_t LCD_EMOTION_MAX = 20;
static constexpr size_t LCD_SUBTITLE_MAX = 64;

class LcdUi : public Ui {
public:
    LcdUi()
        : current_state_(DeviceState::BOOT)
        , dirty_(false)
    {
        status_text_[0]   = '\0';
        emotion_text_[0]  = '\0';
        subtitle_text_[0] = '\0';
    }

    void init() override {
#if defined(ESP_PLATFORM) && defined(CONFIG_LCD_ENABLED)
        lcd_hw_init();
        lcd_clear(0x0000);
#endif
        set_status_label(current_state_);
        dirty_ = true;
    }

    void show_state(DeviceState state) override {
        if (current_state_ != state) {
            current_state_ = state;
            set_status_label(state);
            dirty_ = true;
            flush_if_needed();
        }
    }

    void show_text(const char* text) override {
        if (!text) return;
        strncpy(subtitle_text_, text, LCD_SUBTITLE_MAX - 1);
        subtitle_text_[LCD_SUBTITLE_MAX - 1] = '\0';
        dirty_ = true;
        flush_if_needed();
    }

    void show_emotion(const char* emotion) override {
        if (!emotion) return;
        strncpy(emotion_text_, emotion, LCD_EMOTION_MAX - 1);
        emotion_text_[LCD_EMOTION_MAX - 1] = '\0';
        dirty_ = true;
        flush_if_needed();
    }

    void notify(const char* message) override {
        // Display notification in subtitle row briefly; the next show_text
        // call overwrites it.
        show_text(message);
    }

    void tick(uint32_t /*delta_ms*/) override {
        // Future: scroll long subtitles, animate emotion glyph.
        // Not needed for v1 text-only display.
    }

    // -----------------------------------------------------------------------
    // Inspection helpers (used by host tests — not part of Ui interface)
    // -----------------------------------------------------------------------
    const char* get_status()   const { return status_text_; }
    const char* get_emotion()  const { return emotion_text_; }
    const char* get_subtitle() const { return subtitle_text_; }
    bool        is_dirty()     const { return dirty_; }
    DeviceState get_state()    const { return current_state_; }

private:
    // Maps DeviceState → human-readable label for the status bar.
    static const char* state_label(DeviceState s) {
        switch (s) {
            case DeviceState::BOOT:              return "BOOT";
            case DeviceState::PROVISIONING:      return "PROVISIONING";
            case DeviceState::CONNECTING_WIFI:   return "WIFI";
            case DeviceState::CONNECTING_SERVER: return "SERVER";
            case DeviceState::IDLE:              return "IDLE";
            case DeviceState::LISTENING:         return "LISTENING";
            case DeviceState::THINKING:          return "THINKING";
            case DeviceState::SPEAKING:          return "SPEAKING";
            case DeviceState::UPDATING:          return "UPDATING";
            case DeviceState::FATAL:             return "ERROR";
            default:                             return "?";
        }
    }

    // Maps emotion string → emoji-like ASCII glyph for the centre row.
    static const char* emotion_glyph(const char* emotion) {
        if (!emotion || emotion[0] == '\0') return "( . )";
        if (strcmp(emotion, "happy")       == 0) return "( ^ )";
        if (strcmp(emotion, "sad")         == 0) return "( v )";
        if (strcmp(emotion, "excited")     == 0) return "( ! )";
        if (strcmp(emotion, "questioning") == 0) return "( ? )";
        if (strcmp(emotion, "calm")        == 0) return "( - )";
        return "( . )";  // neutral / unknown
    }

    void set_status_label(DeviceState s) {
        strncpy(status_text_, state_label(s), LCD_STATUS_MAX - 1);
        status_text_[LCD_STATUS_MAX - 1] = '\0';
    }

    void flush_if_needed() {
        if (!dirty_) return;
#if defined(ESP_PLATFORM) && defined(CONFIG_LCD_ENABLED)
        // Future: write status_text_, emotion_glyph(emotion_text_),
        // and subtitle_text_ to the SPI frame buffer.
        // Deferred to Phase 7 when hardware pin assignments are confirmed.
        (void)emotion_glyph;
#endif
        dirty_ = false;
    }

#if defined(ESP_PLATFORM) && defined(CONFIG_LCD_ENABLED)
    // Hardware init stub — implementation deferred until hardware is verified.
    void lcd_hw_init() {
        // TODO: SPI bus init, GPIO config, reset sequence.
        // Pins from boards/breadboard_s3/pins.h (UNVERIFIED):
        //   MOSI=11, SCLK=12, CS=10, DC=13, RST=14, BL=21
    }
    void lcd_clear(uint16_t /*colour*/) {
        // TODO: fill 128x160 framebuffer with given RGB565 colour.
    }
#endif

    DeviceState current_state_;
    bool        dirty_;
    char        status_text_[LCD_STATUS_MAX];
    char        emotion_text_[LCD_EMOTION_MAX];
    char        subtitle_text_[LCD_SUBTITLE_MAX];
};

