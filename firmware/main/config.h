/*
 * firmware/main/config.h — Single source of truth for firmware constants (Rule R4).
 * Values mirror protocol/constants.yaml and Architecture Appendix A.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --------------------------------------------------------------------------
 * Audio sampling rates and frame parameters
 * -------------------------------------------------------------------------- */
#define CONFIG_AUDIO_UP_RATE               16000U
#define CONFIG_AUDIO_UP_CHANNELS           1U
#define CONFIG_AUDIO_UP_FRAME_MS           20U
#define CONFIG_AUDIO_UP_SAMPLES_PER_FRAME  320U  /* (16000 * 20 / 1000) */

#define CONFIG_AUDIO_DN_RATE               24000U
#define CONFIG_AUDIO_DN_CHANNELS           1U
#define CONFIG_AUDIO_DN_FRAME_MS           20U
#define CONFIG_AUDIO_DN_SAMPLES_PER_FRAME  480U  /* (24000 * 20 / 1000) */

/* --------------------------------------------------------------------------
 * Buffer sizing (PSRAM allocated)
 * -------------------------------------------------------------------------- */
/* Microphone ring buffer: 2 seconds of 16 kHz 16-bit mono = 64 KB */
#define CONFIG_MIC_RING_SAMPLES            (CONFIG_AUDIO_UP_RATE * 2U)
#define CONFIG_MIC_PREROLL_MS              200U

/* Jitter buffer: 1.5 seconds of 24 kHz 16-bit mono = 72 KB */
#define CONFIG_JITTER_BUFFER_MS            1500U
#define CONFIG_JITTER_MAX_SAMPLES          (CONFIG_AUDIO_DN_RATE * CONFIG_JITTER_BUFFER_MS / 1000U)
#define CONFIG_PREBUFFER_MS                200U
#define CONFIG_PREBUFFER_SAMPLES           (CONFIG_AUDIO_DN_RATE * CONFIG_PREBUFFER_MS / 1000U)

/* Decode packet queue: up to 100 packets (~2 seconds of downlink audio) */
#define CONFIG_DEC_QUEUE_MAX_PACKETS       100U
#define CONFIG_UPLINK_QUEUE_MAX_FRAMES     10U

/* Room acoustic decay tail after assistant finishes speaking */
#define CONFIG_MIC_TAIL_MS                 300U

/* Safety timeout: device aborts if server never endpoints after 25 seconds */
#define CONFIG_LISTENING_LIMIT_S           25U

/* --------------------------------------------------------------------------
 * Network & Keepalive
 * -------------------------------------------------------------------------- */
#define CONFIG_WS_PING_INTERVAL_S          10U
#define CONFIG_WS_TIMEOUT_S                30U
#define CONFIG_RECONNECT_MAX_BACKOFF_S     30U

#ifdef __cplusplus
}
#endif

