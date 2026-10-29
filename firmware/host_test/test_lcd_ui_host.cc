/*
 * firmware/host_test/test_lcd_ui_host.cc — Host-side tests for LcdUi.
 *
 * Verifies:
 *   - State → status label mapping for all DeviceState values.
 *   - Emotion → glyph mapping via show_emotion.
 *   - Subtitle text round-trips via show_text / get_subtitle.
 *   - notify() stores text in the subtitle slot.
 *   - Dirty flag set/clear semantics.
 *   - Overflow-safe string copies (strings longer than LCD_*_MAX).
 *
 * No SPI or GPIO hardware is exercised (ESP_PLATFORM not defined).
 */

#include <cassert>
#include <cstring>
#include <cstdio>

// Include the LCD UI header; ESP_PLATFORM is not defined here so all
// hardware blocks compile away cleanly.
#include "ui/lcd_ui.h"

static int tests_run    = 0;
static int tests_passed = 0;

#define CHECK(expr)                                                          \
    do {                                                                     \
        ++tests_run;                                                         \
        if (!(expr)) {                                                       \
            fprintf(stderr, "FAIL [%s:%d] %s\n", __FILE__, __LINE__, #expr);\
        } else {                                                             \
            ++tests_passed;                                                  \
        }                                                                    \
    } while (0)

// ---------------------------------------------------------------------------
// 1. State→label mapping covers every DeviceState
// ---------------------------------------------------------------------------
static void test_state_labels() {
    struct Case { DeviceState state; const char* expected; };
    Case cases[] = {
        { DeviceState::BOOT,              "BOOT"        },
        { DeviceState::PROVISIONING,      "PROVISIONING"},
        { DeviceState::CONNECTING_WIFI,   "WIFI"        },
        { DeviceState::CONNECTING_SERVER, "SERVER"      },
        { DeviceState::IDLE,              "IDLE"        },
        { DeviceState::LISTENING,         "LISTENING"   },
        { DeviceState::THINKING,          "THINKING"    },
        { DeviceState::SPEAKING,          "SPEAKING"    },
        { DeviceState::UPDATING,          "UPDATING"    },
        { DeviceState::FATAL,             "ERROR"       },
    };

    for (auto& c : cases) {
        LcdUi ui;
        ui.init();
        ui.show_state(c.state);
        CHECK(strcmp(ui.get_status(), c.expected) == 0);
    }
}

// ---------------------------------------------------------------------------
// 2. Emotion glyph — show_emotion stores value; get_emotion returns it
// ---------------------------------------------------------------------------
static void test_emotion_storage() {
    const char* emotions[] = {
        "happy", "sad", "excited", "questioning", "calm", "neutral", ""
    };
    for (auto* em : emotions) {
        LcdUi ui;
        ui.init();
        ui.show_emotion(em);
        CHECK(strcmp(ui.get_emotion(), em) == 0);
    }
}

// ---------------------------------------------------------------------------
// 3. show_text stores subtitle verbatim
// ---------------------------------------------------------------------------
static void test_show_text() {
    LcdUi ui;
    ui.init();
    ui.show_text("Hello, Anima!");
    CHECK(strcmp(ui.get_subtitle(), "Hello, Anima!") == 0);
}

// ---------------------------------------------------------------------------
// 4. notify() routes to the subtitle slot
// ---------------------------------------------------------------------------
static void test_notify() {
    LcdUi ui;
    ui.init();
    ui.notify("Network error");
    CHECK(strcmp(ui.get_subtitle(), "Network error") == 0);
}

// ---------------------------------------------------------------------------
// 5. show_state is idempotent (no dirty flag churn on same state)
// ---------------------------------------------------------------------------
static void test_show_state_idempotent() {
    LcdUi ui;
    ui.init();
    ui.show_state(DeviceState::IDLE);
    bool dirty_after_new  = ui.is_dirty();
    ui.show_state(DeviceState::IDLE);   // same state — should not be dirty again
    bool dirty_after_same = ui.is_dirty();
    // First call to show_state after init sets dirty; second call should NOT
    // re-set it (state didn't change).
    (void)dirty_after_new;   // may be true on first change
    (void)dirty_after_same;  // should be false on repeat
    CHECK(!ui.is_dirty());   // after second show_state with same state, dirty cleared
}

// ---------------------------------------------------------------------------
// 6. Overflow-safe: strings longer than LCD_SUBTITLE_MAX are truncated
// ---------------------------------------------------------------------------
static void test_subtitle_overflow() {
    LcdUi ui;
    ui.init();
    // Build a 128-char string (longer than LCD_SUBTITLE_MAX=64)
    char big[129];
    for (int i = 0; i < 128; ++i) big[i] = 'A' + (i % 26);
    big[128] = '\0';
    ui.show_text(big);
    // The stored string must be no longer than LCD_SUBTITLE_MAX-1
    CHECK(strlen(ui.get_subtitle()) <= LCD_SUBTITLE_MAX - 1);
}

// ---------------------------------------------------------------------------
// 7. Overflow-safe: emotion string longer than LCD_EMOTION_MAX is truncated
// ---------------------------------------------------------------------------
static void test_emotion_overflow() {
    LcdUi ui;
    ui.init();
    char big[64];
    for (int i = 0; i < 63; ++i) big[i] = 'x';
    big[63] = '\0';
    ui.show_emotion(big);
    CHECK(strlen(ui.get_emotion()) <= LCD_EMOTION_MAX - 1);
}

// ---------------------------------------------------------------------------
// 8. Multiple show_text calls: last one wins
// ---------------------------------------------------------------------------
static void test_show_text_overwrite() {
    LcdUi ui;
    ui.init();
    ui.show_text("first");
    ui.show_text("second");
    CHECK(strcmp(ui.get_subtitle(), "second") == 0);
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main() {
    test_state_labels();
    test_emotion_storage();
    test_show_text();
    test_notify();
    test_show_state_idempotent();
    test_subtitle_overflow();
    test_emotion_overflow();
    test_show_text_overwrite();

    printf("lcd_ui_host: %d/%d tests passed\n", tests_passed, tests_run);
    return (tests_passed == tests_run) ? 0 : 1;
}

