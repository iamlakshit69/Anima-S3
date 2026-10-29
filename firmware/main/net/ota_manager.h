/*
 * firmware/main/net/ota_manager.h — OTA update manager with A/B rollback protection.
 * Architecture Section 7.9 and Rule R11.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

struct OtaOffer {
    char version[32];
    char url[256];
    char sha256[65];
    uint32_t size;
};

enum class OtaStatus {
    IDLE = 0,
    DOWNLOADING,
    VERIFYING,
    SUCCESS,
    FAILED
};

class OtaManager {
public:
    /**
     * @brief Parses an OTA offer from a JSON control message.
     */
    static bool parse_offer(const char* json_str, OtaOffer* out_offer);

    /**
     * @brief Validates manifest integrity: version difference, URL scheme, SHA-256 format, size <= 3 MB.
     */
    static bool validate_manifest(const OtaOffer& offer, const char* current_version);

    /**
     * @brief Initiates asynchronous OTA download into inactive slot.
     */
    static bool start_ota(const OtaOffer& offer);

    /**
     * @brief Marks running partition valid after successful local self-test, canceling rollback.
     */
    static void mark_running_partition_valid();

    /**
     * @brief Manually triggers rollback and reboots to previous partition.
     */
    static void rollback_and_reboot();

    static OtaStatus get_status();
};
