/*
 * firmware/main/audio/wake_word.h — ESP-SR WakeNet and Audio Front-End (AFE) wrapper.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

enum class WakeWordStatus {
    IDLE = 0,
    DETECTED
};

class WakeWordDetector {
public:
    WakeWordDetector();
    ~WakeWordDetector();

    /**
     * @brief Initializes ESP-SR AFE and WakeNet model from flash partition.
     * If model loading fails, PTT remains functional.
     */
    bool init(const char* partition_label = "model");

    /**
     * @brief Feeds 16 kHz 16-bit mono audio block into front-end and WakeNet.
     */
    void feed(const int16_t* pcm, size_t samples);

    /**
     * @brief Polls if wake word was detected in fed audio.
     * @return True if wake word triggered.
     */
    bool fetch_detected();

    void set_armed(bool armed);
    bool is_armed() const;

    const char* get_model_name() const;
    void reset();

private:
    bool armed_;
    bool detected_;
    char model_name_[32];
    void* afe_data_;
};
