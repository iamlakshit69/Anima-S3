/*
 * firmware/main/audio/wake_word.cc — Wake word detector implementation.
 */

#include "audio/wake_word.h"
#include <string.h>
#include <stdio.h>

#if defined(ESP_PLATFORM)
#include "esp_log.h"
#include "esp_spiffs.h"
#include "esp_wn_iface.h"
#include "esp_wn_models.h"
#include "esp_afe_sr_iface.h"
#include "esp_afe_sr_models.h"
static const char* TAG = "wake_word";
static const esp_afe_sr_iface_t* s_afe_handle = nullptr;
#endif

WakeWordDetector::WakeWordDetector()
    : armed_(false),
      detected_(false),
      afe_data_(nullptr) {
    strncpy(model_name_, "Hey Anima (custom/stock)", sizeof(model_name_) - 1);
}

WakeWordDetector::~WakeWordDetector() {
    reset();
}

bool WakeWordDetector::init(const char* partition_label) {
#if defined(ESP_PLATFORM)
    ESP_LOGI(TAG, "Initializing ESP-SR from partition '%s'...", partition_label);

    // Initialize SPIFFS for model partition
    esp_vfs_spiffs_conf_t conf = {
        .base_path = "/srmodel",
        .partition_label = partition_label,
        .max_files = 5,
        .format_if_mount_failed = false
    };
    esp_err_t ret = esp_vfs_spiffs_register(&conf);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Model partition mount failed (%s). Falling back to PTT only.", esp_err_to_name(ret));
        return false;
    }

    s_afe_handle = &ESP_AFE_SR_HANDLE;
    afe_config_t afe_config = AFE_CONFIG_DEFAULT();
    // Rule R2: Half-duplex — AEC disabled
    afe_config.aec_init = false;
    afe_config.se_init = false;
    afe_config.vad_init = false;
    afe_config.wakenet_init = true;
    afe_config.voice_communication_init = false;

    afe_data_ = s_afe_handle->create_from_config(&afe_config);
    if (!afe_data_) {
        ESP_LOGE(TAG, "Failed to create ESP-SR AFE instance");
        return false;
    }

    ESP_LOGI(TAG, "WakeNet armed with model '%s'", model_name_);
    armed_ = true;
    return true;
#else
    (void)partition_label;
    armed_ = true;
    return true;
#endif
}

void WakeWordDetector::feed(const int16_t* pcm, size_t samples) {
    if (!armed_ || !pcm || samples == 0) {
        return;
    }

#if defined(ESP_PLATFORM)
    if (s_afe_handle && afe_data_) {
        s_afe_handle->feed(afe_data_, const_cast<int16_t*>(pcm));
    }
#else
    (void)pcm;
    (void)samples;
#endif
}

bool WakeWordDetector::fetch_detected() {
    if (!armed_) {
        return false;
    }

#if defined(ESP_PLATFORM)
    if (s_afe_handle && afe_data_) {
        afe_fetch_result_t* res = s_afe_handle->fetch(afe_data_);
        if (res && res->wake_word_index > 0) {
            ESP_LOGI(TAG, "Wake word triggered! (index=%d)", res->wake_word_index);
            return true;
        }
    }
    return false;
#else
    if (detected_) {
        detected_ = false;
        return true;
    }
    return false;
#endif
}

void WakeWordDetector::set_armed(bool armed) {
    armed_ = armed;
}

bool WakeWordDetector::is_armed() const {
    return armed_;
}

const char* WakeWordDetector::get_model_name() const {
    return model_name_;
}

void WakeWordDetector::reset() {
#if defined(ESP_PLATFORM)
    if (s_afe_handle && afe_data_) {
        s_afe_handle->destroy(afe_data_);
        afe_data_ = nullptr;
    }
#endif
    armed_ = false;
    detected_ = false;
}
