/*
 * firmware/main/net/ota_manager.cc — OTA update implementation with rollback.
 */

#include "net/ota_manager.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(ESP_PLATFORM)
#include "esp_ota_ops.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static const char* TAG = "ota";
#endif

static OtaStatus s_status = OtaStatus::IDLE;

static bool extract_str(const char* json, const char* key, char* out_buf, size_t out_cap) {
    if (!json || !key || !out_buf || out_cap == 0) return false;
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char* pos = strstr(json, needle);
    if (!pos) return false;
    pos += strlen(needle);
    while (*pos == ' ' || *pos == ':' || *pos == '\t') pos++;
    if (*pos != '\"') return false;
    pos++; // Skip opening quote
    const char* end = strchr(pos, '\"');
    if (!end) return false;
    size_t len = end - pos;
    if (len >= out_cap) len = out_cap - 1;
    memcpy(out_buf, pos, len);
    out_buf[len] = '\0';
    return true;
}

static bool extract_uint(const char* json, const char* key, uint32_t* out_val) {
    if (!json || !key || !out_val) return false;
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char* pos = strstr(json, needle);
    if (!pos) return false;
    pos += strlen(needle);
    while (*pos == ' ' || *pos == ':' || *pos == '\t') pos++;
    char* endptr = nullptr;
    unsigned long val = strtoul(pos, &endptr, 10);
    if (endptr == pos) return false;
    *out_val = static_cast<uint32_t>(val);
    return true;
}

bool OtaManager::parse_offer(const char* json_str, OtaOffer* out_offer) {
    if (!json_str || !out_offer) return false;
    memset(out_offer, 0, sizeof(OtaOffer));

    if (!extract_str(json_str, "version", out_offer->version, sizeof(out_offer->version))) {
        return false;
    }
    if (!extract_str(json_str, "url", out_offer->url, sizeof(out_offer->url))) {
        return false;
    }
    if (!extract_str(json_str, "sha256", out_offer->sha256, sizeof(out_offer->sha256))) {
        return false;
    }
    extract_uint(json_str, "size", &out_offer->size);
    return true;
}

bool OtaManager::validate_manifest(const OtaOffer& offer, const char* current_version) {
    // 1. Must offer a different version
    if (current_version && strcmp(offer.version, current_version) == 0) {
        return false;
    }
    if (strlen(offer.version) == 0) {
        return false;
    }

    // 2. URL must be http or https
    if (strncmp(offer.url, "https://", 8) != 0 && strncmp(offer.url, "http://", 7) != 0) {
        return false;
    }

    // 3. SHA-256 must be exactly 64 hex characters
    if (strlen(offer.sha256) != 64) {
        return false;
    }
    for (size_t i = 0; i < 64; ++i) {
        char c = offer.sha256[i];
        bool is_hex = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
        if (!is_hex) return false;
    }

    // 4. Size check: max 3 MB (3145728 bytes) per partitions.csv ota_0/ota_1
    if (offer.size > 3 * 1024 * 1024) {
        return false;
    }

    return true;
}

bool OtaManager::start_ota(const OtaOffer& offer) {
    if (!validate_manifest(offer, nullptr)) {
        s_status = OtaStatus::FAILED;
        return false;
    }

    s_status = OtaStatus::DOWNLOADING;
#if defined(ESP_PLATFORM)
    ESP_LOGI(TAG, "Starting OTA update: version=%s, url=%s", offer.version, offer.url);

    esp_http_client_config_t http_config = {};
    http_config.url = offer.url;
    http_config.timeout_ms = 10000;
    http_config.keep_alive_enable = true;

    esp_https_ota_config_t ota_config = {};
    ota_config.http_config = &http_config;

    esp_err_t ret = esp_https_ota(&ota_config);
    if (ret == ESP_OK) {
        s_status = OtaStatus::SUCCESS;
        ESP_LOGI(TAG, "OTA upgrade succeeded. Preparing to reboot...");
        return true;
    } else {
        s_status = OtaStatus::FAILED;
        ESP_LOGE(TAG, "OTA upgrade failed: %s", esp_err_to_name(ret));
        return false;
    }
#else
    s_status = OtaStatus::SUCCESS;
    return true;
#endif
}

void OtaManager::mark_running_partition_valid() {
#if defined(ESP_PLATFORM)
    esp_ota_img_states_t ota_state;
    const esp_partition_t* running = esp_ota_get_running_partition();
    if (esp_ota_get_state_partition(running, &ota_state) == ESP_OK) {
        if (ota_state == ESP_OTA_IMG_PENDING_VERIFY) {
            ESP_LOGI(TAG, "Self-test passed! Marking running partition valid, canceling rollback.");
            esp_ota_mark_app_valid_cancel_rollback();
        }
    }
#endif
}

void OtaManager::rollback_and_reboot() {
#if defined(ESP_PLATFORM)
    ESP_LOGW(TAG, "Local self-test failed! Rolling back to previous partition and rebooting.");
    esp_ota_mark_app_invalid_rollback_and_reboot();
#else
    s_status = OtaStatus::FAILED;
#endif
}

OtaStatus OtaManager::get_status() {
    return s_status;
}

