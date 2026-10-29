#include "sys/settings.h"
#include "net/ota_manager.h"
#include "net/ws_client.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    printf("[HOST_TEST] Running test_settings_ota_host...\n");

    // 1. Settings persistence & credentials
    Settings::init();
    assert(Settings::has_credentials());

    Settings::set_volume(85);
    assert(Settings::get().volume == 85);
    Settings::set_volume(200); // clamped to 100
    assert(Settings::get().volume == 100);

    Settings::set_brightness(50);
    assert(Settings::get().brightness == 50);

    Settings::set_wifi("HomeNetwork", "SecretPassphrase");
    assert(strcmp(Settings::get().wifi_ssid, "HomeNetwork") == 0);
    assert(strcmp(Settings::get().wifi_pass, "SecretPassphrase") == 0);

    Settings::set_server("ws://10.0.0.5:8765/v1/device", "token-abc-123");
    assert(strcmp(Settings::get().server_url, "ws://10.0.0.5:8765/v1/device") == 0);
    assert(strcmp(Settings::get().device_token, "token-abc-123") == 0);

    // 2. OTA Manifest Parsing
    const char* valid_json = "{\"version\":\"1.2.0\",\"url\":\"https://ota.anima.lan/firmware.bin\","
                            "\"sha256\":\"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\",\"size\":1500000}";
    OtaOffer offer;
    assert(OtaManager::parse_offer(valid_json, &offer) == true);
    assert(strcmp(offer.version, "1.2.0") == 0);
    assert(strcmp(offer.url, "https://ota.anima.lan/firmware.bin") == 0);
    assert(strcmp(offer.sha256, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef") == 0);
    assert(offer.size == 1500000);

    // Missing fields fail parsing
    const char* invalid_json = "{\"version\":\"1.2.0\"}";
    OtaOffer bad_offer;
    assert(OtaManager::parse_offer(invalid_json, &bad_offer) == false);

    // 3. OTA Manifest Validation (Rule R11 & Architecture 7.9)
    // A. Identical version rejected
    assert(OtaManager::validate_manifest(offer, "1.2.0") == false);
    // B. Different version accepted
    assert(OtaManager::validate_manifest(offer, "1.0.0") == true);

    // C. Invalid URL scheme rejected
    OtaOffer bad_url = offer;
    strncpy(bad_url.url, "ftp://bad/firmware.bin", sizeof(bad_url.url) - 1);
    assert(OtaManager::validate_manifest(bad_url, "1.0.0") == false);

    // D. Invalid SHA-256 (not 64 hex chars) rejected
    OtaOffer bad_hash = offer;
    strncpy(bad_hash.sha256, "short_hash", sizeof(bad_hash.sha256) - 1);
    assert(OtaManager::validate_manifest(bad_hash, "1.0.0") == false);

    // Non-hex characters in hash rejected
    strncpy(bad_hash.sha256, "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdeg", sizeof(bad_hash.sha256) - 1);
    assert(OtaManager::validate_manifest(bad_hash, "1.0.0") == false);

    // E. Image size exceeding 3 MB slot rejected
    OtaOffer bad_size = offer;
    bad_size.size = 4 * 1024 * 1024; // 4 MB > 3 MB slot
    assert(OtaManager::validate_manifest(bad_size, "1.0.0") == false);

    // 4. OTA Execution Simulation
    assert(OtaManager::start_ota(offer) == true);
    assert(OtaManager::get_status() == OtaStatus::SUCCESS);

    assert(OtaManager::start_ota(bad_size) == false);
    assert(OtaManager::get_status() == OtaStatus::FAILED);

    // 5. Auth Error Handling (E_AUTH terminates backoff retries)
    WsClient::set_auth_error(false);
    assert(WsClient::should_retry() == true);

    // Server returns 4401 E_AUTH
    WsClient::set_auth_error(true);
    assert(WsClient::has_auth_error() == true);
    assert(WsClient::should_retry() == false); // stops retrying!

    printf("[HOST_TEST] test_settings_ota_host passed!\n");
    return 0;
}
