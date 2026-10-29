/*
 * THIS FILE IS AUTO-GENERATED — DO NOT EDIT BY HAND.
 * Source: protocol/constants.yaml
 * Generator: protocol/gen.py
 * Generated: 2026-10-29T13:24:03Z
 *
 * R6 (Notes for agents.md): Generated files are never edited by hand.
 *     Change protocol/constants.yaml and run `python protocol/gen.py`.
 */

#pragma once
#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <string.h>  /* memcpy */

/* --------------------------------------------------------------------------
 * Protocol version
 * -------------------------------------------------------------------------- */
#define ANIMA_PROTO_VERSION     1U

/* --------------------------------------------------------------------------
 * Frame header constants
 * -------------------------------------------------------------------------- */
#define ANIMA_HEADER_SIZE       12U

#define ANIMA_KIND_UP           0x01U  /**< audio uplink: device -> server */
#define ANIMA_KIND_DOWN         0x02U  /**< audio downlink: server -> device */

#define ANIMA_FLAG_FIRST        0x01U  /**< bit 0: first frame of this turn stream */
#define ANIMA_FLAG_LAST         0x02U  /**< bit 1: last frame of this turn stream */

/* --------------------------------------------------------------------------
 * Audio settings
 * -------------------------------------------------------------------------- */
/* Uplink (device -> server): 16 kHz Opus mono, 20 ms frames */
#define ANIMA_UP_RATE               16000U
#define ANIMA_UP_CHANNELS           1U
#define ANIMA_UP_FRAME_MS           20U
#define ANIMA_UP_SAMPLES_PER_FRAME  320U
#define ANIMA_UP_BITRATE_MIN        16000U
#define ANIMA_UP_BITRATE_MAX        24000U

/* Downlink (server -> device): 24 kHz Opus mono, 20 ms frames */
#define ANIMA_DN_RATE               24000U
#define ANIMA_DN_CHANNELS           1U
#define ANIMA_DN_FRAME_MS           20U
#define ANIMA_DN_SAMPLES_PER_FRAME  480U
#define ANIMA_DN_BITRATE_MIN        24000U
#define ANIMA_DN_BITRATE_MAX        32000U

/* --------------------------------------------------------------------------
 * Timing constants
 * -------------------------------------------------------------------------- */
#define ANIMA_HELLO_TIMEOUT_S       5U
#define ANIMA_PING_INTERVAL_S       10U
#define ANIMA_SERVER_TIMEOUT_S      30U

/* --------------------------------------------------------------------------
 * Reconnect backoff
 * -------------------------------------------------------------------------- */
#define ANIMA_RECONNECT_MAX_S       30U
/* Steps in seconds: [1, 2, 4, 8, 16, 30] */

/* --------------------------------------------------------------------------
 * Operational constants
 * -------------------------------------------------------------------------- */
#define ANIMA_PACER_LEAD_MS         1000U
#define ANIMA_LISTEN_TIMEOUT_MS     6000U
#define ANIMA_MAX_TURN_MS           20000U
#define ANIMA_FIXED_SILENCE_MS      700U
#define ANIMA_SILENCE_MAX_MS        1100U
#define ANIMA_TOOL_TIMEOUT_MS       2000U
#define ANIMA_PREBUFFER_MS          200U
#define ANIMA_JITTER_BUFFER_MS      1500U
#define ANIMA_MIC_TAIL_MS           300U
#define ANIMA_LISTENING_LIMIT_S     25U

/* --------------------------------------------------------------------------
 * Binary frame header struct (little-endian, packed, 12 bytes)
 *
 * Wire layout:
 *   offset  size  type   field
 *   0       1     u8     kind    (ANIMA_KIND_UP / ANIMA_KIND_DOWN)
 *   1       1     u8     flags   bit0=ANIMA_FLAG_FIRST, bit1=ANIMA_FLAG_LAST
 *   2       2     u16le  seq     per-direction frame counter, wraps at 2^16
 *   4       4     u32le  turn    turn id
 *   8       4     u32le  t_ms    sender timestamp ms
 *   12      n     bytes  opus    one Opus packet
 * -------------------------------------------------------------------------- */
#pragma pack(push, 1)
typedef struct {
    uint8_t  kind;    /**< ANIMA_KIND_UP or ANIMA_KIND_DOWN */
    uint8_t  flags;   /**< FLAG_FIRST | FLAG_LAST bitmask */
    uint16_t seq;     /**< little-endian, per-direction counter */
    uint32_t turn;    /**< little-endian, turn id */
    uint32_t t_ms;    /**< little-endian, sender timestamp ms */
    /* opus payload follows immediately in the WebSocket binary message */
} AnimaFrameHeader;
#pragma pack(pop)

/** Minimum valid frame length (header only, no Opus payload). */
#define ANIMA_FRAME_MIN_LEN  sizeof(AnimaFrameHeader)

/* --------------------------------------------------------------------------
 * Inline helpers — encode and decode the 12-byte header.
 * The device is little-endian (ESP32), so plain struct access is correct.
 * -------------------------------------------------------------------------- */

/**
 * @brief Fill @p hdr from the raw @p data bytes received over WebSocket.
 * @return 1 on success, 0 if @p len is too short or kind is unknown.
 */
static inline int anima_frame_decode(const uint8_t *data, size_t len,
                                      AnimaFrameHeader *hdr)
{
    if (len < sizeof(AnimaFrameHeader)) return 0;
    memcpy(hdr, data, sizeof(AnimaFrameHeader));
    /* ESP32 is little-endian; host tests on x86 are also little-endian.
     * If porting to a big-endian host, byte-swap seq, turn and t_ms here. */
    if (hdr->kind != ANIMA_KIND_UP && hdr->kind != ANIMA_KIND_DOWN) return 0;
    return 1;
}

/**
 * @brief Write the 12-byte header into @p buf (which must be at least 12 bytes).
 */
static inline void anima_frame_encode(uint8_t *buf, uint8_t kind, uint8_t flags,
                                       uint16_t seq, uint32_t turn, uint32_t t_ms)
{
    AnimaFrameHeader hdr;
    hdr.kind  = kind;
    hdr.flags = flags;
    hdr.seq   = seq;
    hdr.turn  = turn;
    hdr.t_ms  = t_ms;
    memcpy(buf, &hdr, sizeof(hdr));
}

/* --------------------------------------------------------------------------
 * Error code string constants
 * -------------------------------------------------------------------------- */
#define ANIMA_ERR_E_PROTO_VERSION        "E_PROTO_VERSION"
#define ANIMA_ERR_E_AUTH                 "E_AUTH"
#define ANIMA_ERR_E_BAD_FRAME            "E_BAD_FRAME"
#define ANIMA_ERR_E_STT_FAIL             "E_STT_FAIL"
#define ANIMA_ERR_E_LLM_FAIL             "E_LLM_FAIL"
#define ANIMA_ERR_E_TTS_FAIL             "E_TTS_FAIL"
#define ANIMA_ERR_E_TOOL_DENIED          "E_TOOL_DENIED"
#define ANIMA_ERR_E_TOOL_TIMEOUT         "E_TOOL_TIMEOUT"
#define ANIMA_ERR_E_BUSY                 "E_BUSY"
#define ANIMA_ERR_E_INTERNAL             "E_INTERNAL"

/* --------------------------------------------------------------------------
 * Message type string constants
 * -------------------------------------------------------------------------- */
/* device to server */
#define ANIMA_MSG_HELLO                  "hello"
#define ANIMA_MSG_LISTEN_START           "listen.start"
#define ANIMA_MSG_LISTEN_END             "listen.end"
#define ANIMA_MSG_ABORT                  "abort"
#define ANIMA_MSG_TOOL_RESULT            "tool.result"
#define ANIMA_MSG_PLAYBACK               "playback"
#define ANIMA_MSG_TELEMETRY              "telemetry"

/* server to device */
#define ANIMA_MSG_HELLO_ACK              "hello_ack"
#define ANIMA_MSG_LISTEN_STOP            "listen.stop"
#define ANIMA_MSG_STT                    "stt"
#define ANIMA_MSG_REPLY                  "reply"
#define ANIMA_MSG_TTS_START              "tts.start"
#define ANIMA_MSG_TTS_STOP               "tts.stop"
#define ANIMA_MSG_TOOL_CALL              "tool.call"
#define ANIMA_MSG_ALERT                  "alert"
#define ANIMA_MSG_ERROR                  "error"


#ifdef __cplusplus
} /* extern "C" */
#endif
