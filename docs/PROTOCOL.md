# ANIMA-S3 Wire Protocol v1

> This document is generated from section 4 of `docs/ARCHITECTURE.md` and kept in sync with `protocol/`.
> The authoritative machine-readable definitions are `protocol/constants.yaml`, `protocol/schema.json`, and `protocol/vectors.json`.
> The generated code lives in `server/anima_server/transport/protocol_gen.py` and `firmware/main/net/protocol_gen.h` — do **not** edit those files by hand (R6).

---

## 1. Connection and handshake

- Device connects to `ws://<host>:<port>/v1/device`. Host comes from NVS settings, with mDNS (`anima.local`) as fallback.
- HTTP upgrade carries `Authorization: Bearer <device_token>` and `X-Device-Id`. Server closes with code 4401 if the token is wrong.
- First message from the device must be `hello` within **5 s**. Server replies `hello_ack`. If `proto` is not supported, server sends `error` with `E_PROTO_VERSION` and closes.
- Binary frames are audio. Text frames are JSON objects with a `type` field.

---

## 2. Binary audio frame

Little-endian (ESP32 native). One WebSocket binary message holds exactly one Opus packet. The payload length is the WebSocket frame length minus 12.

```
offset  size  type   field
0       1     u8     kind     0x01 = audio uplink  (device → server)
                              0x02 = audio downlink (server → device)
1       1     u8     flags    bit0 = FLAG_FIRST (first frame of the turn stream)
                              bit1 = FLAG_LAST  (last frame of the turn stream)
2       2     u16le  seq      per-direction frame counter, wraps at 2^16
4       4     u32le  turn     turn id (device-authoritative u32)
8       4     u32le  t_ms     sender timestamp ms since start of this stream
12      n     bytes  opus     one Opus packet (20 ms)
```

**Uplink Opus settings:** 16 kHz, mono, 20 ms, VOIP, 16–24 kbps.
**Downlink Opus settings:** 24 kHz, mono, 20 ms, VOIP, 24–32 kbps.

The `hello` message states the settings so both sides can verify them.

---

## 3. JSON messages

Every message is a JSON object with a `type` string field. Messages that belong to a turn carry `turn`. Non-turn-scoped messages: `hello`, `hello_ack`, `alert`, `error`, `telemetry`.

### 3.1 Device → Server

| Type | Required fields | Optional fields |
|---|---|---|
| `hello` | `proto`, `device_id`, `fw`, `board`, `features`, `audio`, `tools`, `last_turn` | — |
| `listen.start` | `turn`, `reason` (`wake_word`\|`button`\|`barge_in`) | `wake_word` |
| `listen.end` | `turn` | — |
| `abort` | `turn` | — |
| `tool.result` | `turn`, `id`, `ok` | `result`, `error` |
| `playback` | `turn`, `event` (`started`\|`finished`\|`underrun`\|`flushed`), `buffered_ms` | — |
| `telemetry` | `state`, `rssi`, `heap_free`, `psram_free`, `uptime_s` | `battery` |

### 3.2 Server → Device

| Type | Required fields | Optional fields |
|---|---|---|
| `hello_ack` | `proto`, `session_id`, `server`, `listen_timeout_ms`, `max_turn_ms` | `ota` |
| `listen.stop` | `turn`, `reason` (`endpoint`\|`no_speech`\|`max_len`\|`error`) | — |
| `stt` | `turn`, `text` | — |
| `reply` | `turn`, `text` | `emotion` |
| `tts.start` | `turn` | — |
| `tts.stop` | `turn`, `reason` (`done`\|`aborted`\|`error`) | — |
| `tool.call` | `turn`, `id`, `name`, `args`, `timeout_ms` | — |
| `alert` | `level` (`info`\|`warn`\|`error`), `code`, `text` | — |
| `error` | `code`, `text`, `fatal` | — |

### 3.3 Nested types

**ToolSpec** (inside `hello.tools`):
```json
{ "name": "set_volume", "description": "...", "params": { /* JSON Schema */ }, "risk": "safe" }
```

**OtaOffer** (inside `hello_ack.ota`):
```json
{ "version": "1.2.3", "url": "https://...", "sha256": "<64-hex>", "size": 1048576 }
```

**AudioSettings** (inside `hello.audio.up` and `hello.audio.down`):
```json
{ "codec": "opus", "rate": 16000, "frame_ms": 20 }
```

Full JSON Schema: `protocol/schema.json`.

---

## 4. Error codes

| Code | Meaning | Device behaviour |
|---|---|---|
| `E_PROTO_VERSION` | Unsupported protocol version | Show error, retry with backoff |
| `E_AUTH` | Bad or missing token | Show error, stop retrying until reconfigured |
| `E_BAD_FRAME` | Malformed binary frame | Log, continue |
| `E_STT_FAIL` | Transcription failed | Play error chime, return to IDLE |
| `E_LLM_FAIL` | LLM unreachable after retries | Server speaks a fallback apology |
| `E_TTS_FAIL` | Synthesis failed | Server plays an error tone |
| `E_TOOL_DENIED` | Tool not in allowlist or policy refused | Reported to LLM as a tool error |
| `E_TOOL_TIMEOUT` | Device did not answer in time | Reported to LLM as a tool error |
| `E_BUSY` | Server at session capacity | Retry with backoff |
| `E_INTERNAL` | Unexpected server fault | Return to IDLE |

---

## 5. Keepalive and reconnect

- Device sends a WebSocket ping every **10 s**. Server closes after **30 s** of silence.
- Device reconnects with exponential backoff and jitter: **1, 2, 4, 8, 16, 30 s** (+ up to 20% jitter). It sends a new `hello` with `last_turn`; the server starts a fresh session. Any turn in progress is abandoned.
- Server restarts must not require touching the device.

---

## 6. Key constants

All values are defined in `protocol/constants.yaml`. The generated code is the only authoritative source in each language.

| Constant | Value |
|---|---|
| `PROTO_VERSION` | 1 |
| `HEADER_SIZE` | 12 bytes |
| `KIND_UP` | 0x01 |
| `KIND_DOWN` | 0x02 |
| `FLAG_FIRST` | 0x01 (bit 0) |
| `FLAG_LAST` | 0x02 (bit 1) |
| Uplink: rate / frame_ms / samples_per_frame | 16000 / 20 / 320 |
| Downlink: rate / frame_ms / samples_per_frame | 24000 / 20 / 480 |
| `HELLO_TIMEOUT_S` | 5 |
| `PING_INTERVAL_S` | 10 |
| `SERVER_TIMEOUT_S` | 30 |
| Reconnect backoff steps (s) | 1, 2, 4, 8, 16, 30 |
| `PACER_LEAD_MS` | 1000 |
| `LISTEN_TIMEOUT_MS` | 6000 |
| `MAX_TURN_MS` | 20000 |
| `FIXED_SILENCE_MS` | 700 |
| `TOOL_TIMEOUT_MS` | 2000 |
| `PREBUFFER_MS` | 200 |
| `JITTER_BUFFER_MS` | 1500 |
| `MIC_TAIL_MS` | 300 |

---

## 7. Example sequences

### A. Normal turn

```
D  listen.start(turn=7, reason=wake_word)    D  audio frames turn=7 ...
S  listen.stop(7, endpoint)                  S  stt(7, text)
S  tts.start(7)                              S  audio frames turn=7 ... (LAST set on final frame)
S  reply(7, sentence)                        S  tts.stop(7, done)
D  playback(7, finished)                     D  state IDLE
```

### B. Barge-in

```
D  (SPEAKING turn=7) button pressed: flush playback, turn=8
D  listen.start(turn=8, reason=barge_in)     D  audio frames turn=8 ...
S  sees 8 > 7: cancels turn 7 tasks, drops queued turn 7 work
```

### C. Tool call

```
S  tool.call(7, id=a1, name=set_volume, args={level:40}, timeout_ms=2000)
D  policy check, execute                     D  tool.result(7, a1, ok=true)
S  feeds the result to the LLM and continues the reply
```

### D. No speech

```
D  listen.start(turn=9)                      S  no speech within listen_timeout_ms
S  listen.stop(9, no_speech)                 D  state IDLE
```

---

## 8. Protocol change process

To add or change a message type:
1. Update `protocol/schema.json`
2. Update `protocol/constants.yaml`
3. Update `protocol/vectors.json` with new test vectors
4. Run `python protocol/gen.py` to regenerate both language outputs
5. Update both server and firmware implementations
6. Update this document and `CHANGELOG.md`

All changes to the protocol must land in a single commit/PR with both sides updated.
