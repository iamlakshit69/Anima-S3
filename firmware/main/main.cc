/*
 * firmware/main/main.cc — Firmware entry point (app_main).
 */

#include "app/app.h"
#include "audio/audio_io.h"
#include "boards/board.h"
#include "sys/settings.h"
#include "ui/ui.h"

#if defined(ESP_PLATFORM)
#include "esp_log.h"
static const char* TAG = "main";

extern "C" void app_main() {
    ESP_LOGI(TAG, "Starting ANIMA-S3 Firmware v0.1.0...");

    // 1. Storage & Settings
    Settings::init();

    // 2. Hardware Board GPIO
    Board* board = Board::get();
    board->init_gpio();

    // 3. User Interface (Status LED)
    Ui::get()->init();

    // 4. Audio I/O (INMP441 & MAX98357A)
    AudioIO::init();

    // 5. Application loop
    App& app = App::instance();
    app.init();
    app.run();
}
#else
int main() {
    return 0;
}
#endif
