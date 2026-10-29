# CHANGELOG

All notable changes to ANIMA-S3 are recorded here.
Format: `## [Phase N] YYYY-MM-DD — brief title` followed by a bullet list.

---

## [Phase 7] 2026-10-29 — Hardening, soak testing, diagnostics, packaging, and user guide

### Added
- **`server/anima_server/diagnostics/` (`anima_check.py`)** — Port of ANIMA health checker
  architecture (§6.13). Features:
  - `ConfigCollector`: Validates all configuration invariants.
  - `SttCollector`: Exercises Whisper transcription using test audio arrays.
  - `LlmCollector`: Verifies provider API key and model parameters without invoking paid APIs.
  - `TtsCollector`: Tests speech synthesis generation with Kokoro TTS.
  - `WsLoopbackCollector`: Validates WebSocket transport configuration.
  - Health gates: Evaluates `ttfa_p50_s` against warning (1.5s) and failure (2.5s) thresholds.
  - Formatted text report generator and `diff_reports` utility to track health differences.
- **`server/tests/test_diagnostics.py`** — 10 unit tests for all diagnostic collectors, report
  generation, report rendering, and report diffing.
- **`tools/soak_test.py`** — Automated soak testing script running configurable iterations (default 20)
  of complete dialogue turns against an in-process fake server. Computes TTFA p50 and p95 metrics and
  monitors stability.
- **`firmware/host_test/test_soak_host.cc`** — C++ host test executing 100 continuous dialogue cycles
  and 50 barge-in cycles across the table-driven state machine, verifying memory stability and
  deterministic transition handling.
- **`docs/WSS_SETUP.md`** — Comprehensive TLS/WSS setup guide with self-signed certificate generation,
  Let's Encrypt instructions, server configuration, and ESP-IDF CA certificate embedding.
- **Docker & systemd packaging**:
  - `server/Dockerfile`: Container image based on `python:3.11-slim` with system `libopus`.
  - `server/docker-compose.yml`: Multi-service compose file with cache volume mounting.
  - `server/requirements.txt`: Frozen production requirements list.
  - `server/anima_server.service`: Hardened systemd service unit with `NoNewPrivileges` and isolation.
- **`docs/USER_GUIDE.md`** — Complete user guide detailing hardware requirements, pinout reference,
  native & containerized server setup, firmware flashing guidelines, provisioning, daily operations,
  OTA process, and troubleshooting.
- **`ci.sh`** — Root continuous integration runner executing protocol vector tests, server test suite,
  C++ host test suite, and system diagnostics.

### Changed
- **`server/anima_server/audio/endpointer.py`**: Added `partial_text` parameter to `Endpointer.feed()`,
  routing partial transcripts into `SemanticPolicy.decide()`.
- **`server/anima_server/pipeline/ingest.py`**: Wired `partial_text` feed using `session.partial_stt_text`.
- **`server/anima_server/transport/session.py`**: Added `partial_stt_text` attribute placeholder.
- **`firmware/host_test/CMakeLists.txt`**: Registered `test_soak_host` (11th test executable).

### Test run (2026-10-29)
```
C++ host tests : ctest --test-dir firmware/host_test/build → 11/11 passed (100%)
Python server  : PYTHONPATH=server pytest server/tests     → 89/89 passed (100%)
Protocol tests : PYTHONPATH=. pytest protocol/tests       → 51/51 passed (100%)
Soak test      : python tools/soak_test.py --turns 5       → 5/5 turns passed (TTFA p50=0.025s)
CI runner      : ./ci.sh                                   → ALL TEST SUITES PASSED (GREEN)
```

---

## [Phase 6] 2026-10-29 — LCD UI, emotion classification, and semantic endpointing

### Added
- **`firmware/main/ui/lcd_ui.h`** — `LcdUi` class implementing the `Ui` interface for a
  128×160 ST7735/ST7789-compatible panel. Provides `show_state`, `show_text`, `show_emotion`,
  and `notify`. Status bar (state label), emotion glyph (ASCII face), and subtitle row. All
  SPI/GPIO hardware calls are gated behind `#if ESP_PLATFORM && CONFIG_LCD_ENABLED` so host
  tests compile without any ESP-IDF dependency. **Pin assignments are AI-generated unverified
  defaults; see `docs/HARDWARE.md` before flashing.**
- **`firmware/host_test/test_lcd_ui_host.cc`** — 8 cases: state→label mapping, emotion
  storage, subtitle round-trip, notify routing, idempotent show_state, overflow-safe copies
  for subtitle and emotion, last-write-wins on multiple show_text calls.
- **`server/anima_server/pipeline/emotion.py`** — Lightweight regex-heuristic emotion
  classifier. Six categories: `happy`, `sad`, `calm`, `excited`, `questioning`, `neutral`.
  No external model; evaluates in priority order (questioning → excited → happy → sad →
  calm → neutral). Verified: no third-party libraries required.
- **`server/anima_server/audio/endpointer.py` — `SemanticPolicy`** — Phase 6 endpoint policy.
  Ends the turn early (~400 ms silence) if the partial transcript is a "finished thought"
  (sentence-final punctuation, complete question, or command form); waits up to
  `silence_max_ms` (default 1100 ms) otherwise. Satisfies `EndOfTurnPolicy` protocol and
  is backward-compatible with `FixedPolicy`.
- **Config: `semantic_endpointing: bool = False`** and **`semantic_early_silence_ms: int = 400`**
  in `Config` dataclass; loaded from `SEMANTIC_ENDPOINTING` and `SEMANTIC_EARLY_SILENCE_MS`
  env vars. Default off.
- **Emotion wired into egress** — `egress_stage` calls `emotion.classify(text)` on each
  phrase and populates the `emotion` field of `ReplyMsg` before sending it to the device.
  The device can use this to drive the LCD emotion glyph.
- **SemanticPolicy wired into session** — `Session.__init__` checks `cfg.semantic_endpointing`
  and instantiates either `SemanticPolicy` or `FixedPolicy` accordingly.

### Tests
- `server/tests/test_emotion.py` — 22 cases covering all six emotion categories, empty
  input, whitespace, priority ordering, and the return-type contract.
- `server/tests/test_endpointer.py` — extended with 12 SemanticPolicy cases: unit-level
  `decide()` for finished/unfinished thoughts, `None` partial text, `?` sentence endings,
  command detection, protocol conformance, and integration with `Endpointer`.
- `firmware/host_test/test_lcd_ui_host.cc` — 8 cases (see Added above).

### Test run (2026-10-29)
```
C++ host tests : ctest --test-dir firmware/host_test/build → 10/10 passed
Python server  : PYTHONPATH=server .venv/bin/python -m pytest server/tests -q → 79/79 passed
Protocol tests : PYTHONPATH=. .venv/bin/python -m pytest protocol/tests -q → 51/51 passed
```

### Not changed / deferred
- LCD SPI hardware driver (`lcd_hw_init`, `lcd_clear`) — deferred to Phase 7; requires
  confirmed hardware wiring in `docs/HARDWARE.md`.
- Streaming TTS — architecture lists it as optional for Phase 6; `kokoro-onnx` streaming
  API is unverified against the installed version (R14). Deferred to Phase 7.
- Partial transcript plumbing from STT to Endpointer — the `Endpointer.feed()` call does
  not yet receive a `partial_text` argument from the STT stage. SemanticPolicy is fully
  exercised via unit tests and can be wired into STT streaming in Phase 7.

---

## [Phase 5] 2026-10-29 — Provisioning, settings, OTA with rollback, admin API

### Added
- **Authenticated Admin API & OTA Authority**:
  - `server/anima_server/admin/api.py`: Implemented standalone HTTP Admin API service on separate port (`8766`) with bearer token authentication (`admin_token`).
  - Endpoints:
    - `GET /healthz`: Server health check, uptime, and active session count.
    - `GET /metrics`: Aggregated performance counters and active connection metrics.
    - `GET /ota/manifest`: Rule R11-compliant firmware manifest delivery (`version`, `url`, `sha256`, `size`).
  - `server/tests/test_admin_api.py`: 4 unit tests verifying token authorization (401 on missing/invalid token), healthz reporting, and manifest responses.
  - Integrated `start_admin_api` supervisor into `server/anima_server/main.py`.
- **Firmware Settings & NVS Persistence**:
  - `firmware/main/sys/settings.h`/`.cc`: Added credential validation (`has_credentials()`), persistent Wi-Fi SSID/password, server URL, device token, and volume/brightness setters with clamping.
- **A/B OTA Update Engine with Rollback Protection**:
  - `firmware/main/net/ota_manager.h`/`.cc`: Manifest parser and integrity validator checking version differentiation, HTTPS/HTTP URLs, 64-character SHA-256 verification, and 3 MB slot constraint.
  - Rollback protection: `mark_running_partition_valid()` cancels rollback only after successful post-boot self-test (`AudioIO` + Wi-Fi). If self-test fails, `rollback_and_reboot()` automatically reverts to the previous working partition slot.
- **Terminal E_AUTH Handling**:
  - `firmware/main/net/ws_client.h`/`.cc`: Added `set_auth_error()` and `should_retry()` checks. On 4401 (`E_AUTH`), backoff reconnection is stopped immediately to prevent futile retry loops.
- **Host Test Suite**:
  - `firmware/host_test/test_settings_ota_host.cc`: Added host tests verifying settings persistence, OTA manifest parsing & integrity validation, size limits, simulated OTA execution, and `E_AUTH` retry termination.

### Tests
```sh
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 9/9 host tests passed (100%)
.venv/bin/python -m pytest server/tests protocol/tests -q           → 98/98 tests passed (100%)
```

---

## [Phase 4] 2026-10-29 — Tools, fast-path intents, endpoint tuning

### Added
- **Device Tool Registry & Security Allowlist**:
  - `firmware/main/sys/tools.h`/`.cc`: Implemented device-side tool registry with strict risk gating (`ToolRisk::SAFE`) and forbidden capability blocking (Rule R7: `reboot`, `upgrade_firmware`, `wifi_*`, `factory_reset`, `set_token`).
  - Added 4 safe hardware tools:
    - `set_volume`: Speaker volume control with [0, 100] clamping.
    - `set_brightness`: Screen brightness control with [0, 100] clamping.
    - `lamp_set`: Relay switching (PIN 18, default low at boot) with device-side rate limiting (max 10 toggles/min).
    - `get_status`: Telemetry reporting (battery percentage, current volume, Wi-Fi RSSI).
  - Wired `App::on_tool_call` with turn matching, argument validation, and `tool.result` responses.
  - `firmware/host_test/test_tools_host.cc`: Added host tests verifying tool lookups, parameter clamping, schema validation errors, and rejection of forbidden and unlisted tools.
- **Fast-Path Intent Engine**:
  - `server/anima_server/pipeline/intents.py`: Pattern-matched regex engine for high-frequency commands:
    - Volume adjustments: "volume up", "volume down", "set volume to N" (relative steps and absolute values).
    - Appliance control: "turn on/off the lamp", "switch on/off the light".
    - System status & time: "what time is it", "tell me the time".
    - Conversational stop: "stop", "be quiet", "cancel" (aborts playback/turn without speech).
  - Bypasses LLM round-trip: directly triggers tool execution via device proxy, formats canned spoken replies, and pushes immediately to TTS `token_q`.
  - Wired into `llm_stage` in `server/anima_server/pipeline/llm.py` before provider call; respects `cfg.fast_path_intents` flag.
  - `server/tests/test_intents.py`: Added 6 unit tests covering regex patterns, tool execution, canned reply generation, and LLM bypass verification.
- **Device Proxy & End-to-End Integration**:
  - `server/tests/test_device_proxy.py`: Added tests for `E_TOOL_DENIED` and ignoring late results arriving after timeout.
  - `server/tests/test_integration.py`: Added `test_scenario_tool_call_end_to_end` asserting full two-round LLM tool invocation (`lamp_set` -> device proxy -> `tool.call` -> `tool.result` -> assistant reply audio).

### Tests
```sh
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 8/8 host tests passed (100%)
.venv/bin/python -m pytest server/tests protocol/tests -q           → 94/94 tests passed (100%)
```

---

## [Phase 3] 2026-10-29 — Wake word, full state machine, reconnect drills

### Added
- **Wake Word & AFE (Audio Front-End)**:
  - `firmware/main/audio/wake_word.h`/`.cc`: ESP-SR AFE and WakeNet wrapper for wake word detection. Configured strictly half-duplex with AEC disabled (Rule R2). Loads models from SPIFFS `model` partition (`0x620000`, 4 MB). Arms/disarms wake detection and gracefully falls back to PTT if model partition is unmounted or missing.
  - `firmware/host_test/test_wake_word_host.cc`: Host test verifying arm/disarm, audio block feeding, reset, and model query.
- **Full State Machine & Task Architecture**:
  - `firmware/main/app/app_context.h`: Abstract `AppContext` interface decoupling transitions, state handling, and unit test mocks.
  - `firmware/main/app/state_machine.h`/`.cc`: Extended table-driven state machine with 27 transitions implementing complete Architecture § 7.5 specification (boot, Wi-Fi timeout, server connection, wake word & PTT turns, listening timeout watchdog, TTS playback, barge-in interrupts, OTA updates, and disconnects).
  - `firmware/main/app/app.h`/`.cc`: Complete FreeRTOS task architecture with core pinning (Core 1: `audio_in` pri 9, `afe_wake` pri 8, `audio_out` pri 9; Core 0: `opus_enc` pri 5, `opus_dec` pri 6). Downlink packet queuing (100 packets), 25s listening timeout watchdog, 300ms room decay tail before unmuting mic (`CONFIG_MIC_TAIL_MS`).
  - `firmware/host_test/test_state_machine_host.cc`: Expanded host tests verifying all 27 transitions with a `MockAppContext` executing every action, invalid event rejection, and stale-turn event dropping.
- **Reconnect & Disconnect Drills**:
  - `server/tests/test_integration.py`: Added `test_scenario_reconnect` (client completes turn 1, disconnects, reconnects with fresh handshake carrying `last_turn=1`, completes turn 2 with all frames matching turn 2) and `test_scenario_disconnect_mid_stream` (client starts turn, sends audio, and abruptly closes socket; verifies server shuts down scope cleanly without unhandled exceptions).
  - `tools/fake_device.py`: Verified `--scenario reconnect` end-to-end drill.

### Tests
```sh
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 7/7 host tests passed (100%)
.venv/bin/python -m pytest server/tests protocol/tests -v            → 85/85 tests passed (100%)
```

---

## [Phase 2] 2026-10-29 — Firmware audio loop (PTT, LED UI, self-test)

### Added
- **Hardware Abstraction & Pin Mapping**:
  - `firmware/main/boards/breadboard_s3/pins.h`: Pin map verified against `docs/HARDWARE.md` for ESP32-S3 N16R8 (INMP441 on GPIO 4,5,6; MAX98357A on GPIO 7,15,16; BOOT GPIO 0; PTT GPIO 47; Status LED GPIO 48; avoiding reserved Octal PSRAM GPIO 26-37).
  - `firmware/main/boards/board.h` & `breadboard_s3/board.cc`: Hardware abstraction interface and GPIO initializer.
- **Audio I/O & Buffers**:
  - `firmware/main/audio/ring_buffer.h`: Lock-free Single-Producer Single-Consumer (SPSC) circular buffer supporting pre-roll discard and zero dynamic heap allocation in audio loops.
  - `firmware/main/audio/jitter_buffer.h`/`.cc`: 24 kHz playback jitter buffer with 200ms prebuffer threshold, underrun detection, and barge-in clear.
  - `firmware/main/audio/audio_io.h`/`.cc`: I2S driver for INMP441 RX (16 kHz, 32-bit slot conversion to 16-bit) and MAX98357A TX (24 kHz mono standard Philips), half-duplex mic muting, and speaker DMA zeroing.
  - `firmware/main/audio/opus_enc.h`/`.cc` & `audio/opus_dec.h`/`.cc`: 16 kHz VOIP Opus encoder and 24 kHz Opus decoder.
  - `firmware/main/audio/cues.h`/`.cc`: Acoustic chime synthesis (wake cue, ready cue, error buzz).
- **Control & State Machine**:
  - `firmware/main/sys/buttons.h`/`.cc`: Debounced button handler for PTT (down/up) and BOOT (tap barge-in vs long-press provisioning).
  - `firmware/main/app/events.h` & `app/state_machine.h`/`.cc`: Table-driven transition engine with 21 transitions covering boot, wifi/ws reconnect, PTT turns, barge-in interrupts, and unhandled event rejection.
  - `firmware/main/ui/ui.h` & `ui/led_ui.cc`: LED pattern generator (IDLE off, LISTENING solid on, THINKING slow blink, SPEAKING fast pulse, PROVISIONING double blink).
  - `firmware/main/sys/diag.h`/`.cc`: Self-test mode, free heap/PSRAM reporting, and microphone audio analysis (clipping & dead mic detection).
  - `firmware/main/net/ws_client.h`/`.cc`: WebSocket transport with exponential backoff & 20% jitter.
  - `firmware/main/app/app.h`/`.cc` & `main.cc`: Application coordinator and FreeRTOS task integration.
- **Host Test Suite**:
  - `test_ring_buffer_host`: Tests SPSC circular wraparound, overflow, underflow, and pre-roll trim.
  - `test_jitter_buffer_host`: Tests 200ms prebuffer threshold, underruns, and barge-in clear.
  - `test_buttons_host`: Tests PTT down/up debounce, short tap, and >3s long press.
  - `test_state_machine_host`: Tests all 21 table-driven transitions, barge-in, and unhandled event rejection.
  - `test_diag_host`: Tests microphone clipping detection, silence detection, and memory metrics.

### Tests
```sh
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 6 passed (100%)
.venv/bin/python -m pytest server/tests -v                           → 32 passed (100%)
.venv/bin/python -m pytest protocol/tests -v                         → 51 passed (100%)
```

---

## [Phase 1] 2026-10-29 — Server with fake device

### Added
- **Core Pipeline Components**:
  - `server/anima_server/core/turn.py`: `TurnScope` managing task tracking and cancellation per turn (Rule T6).
  - `server/anima_server/core/sentinel.py`: Pipeline markers (`END_OF_RESPONSE`, `END_OF_SPEECH`).
  - `server/anima_server/core/retry.py`: Exponential backoff with jitter and error tone generator.
  - `server/anima_server/core/metrics.py`: `TurnLatency` (endpoint, STT, LLM TTFT, TTS, TTFA) and `SessionMetrics`.
  - `server/anima_server/core/supervisor.py`: Stage supervision restarting on transient errors and terminating session on crash threshold (5 in 60s).
- **Audio Processing & Codecs**:
  - `server/anima_server/audio/opus_codec.py`: `OpusDecoder` with Packet Loss Concealment (PLC on 1-3 packet gaps) and `OpusEncoder` with 20ms re-chunking and zero-padding flush.
  - `server/anima_server/audio/rechunk.py`: Fixed-size block re-chunker (512-sample blocks for VAD).
  - `server/anima_server/audio/vad.py`: `SileroVAD` (ONNX runtime + RMS energy fallback) and deterministic `FakeVAD`.
  - `server/anima_server/audio/endpointer.py`: `Endpointer` state machine with `FixedPolicy`, onset hysteresis, no-speech timeout, and PTT `force_end`.
  - `server/anima_server/audio/dsp.py`: Peak normalization, RMS calculation, trailing silence trimming, Whisper hallucination filter.
- **Pipeline Stages**:
  - `server/anima_server/pipeline/ingest.py`: Decodes uplink Opus frames and feeds the endpointer.
  - `server/anima_server/pipeline/stt.py`: Transcribes audio with Whisper, enforces minimum audio duration and filters hallucinations.
  - `server/anima_server/pipeline/llm.py`: History management, streaming token accumulator, fallback apology, and tool execution loop.
  - `server/anima_server/pipeline/tts.py`: Token accumulator with early first-phrase release and Kokoro speech synthesis.
  - `server/anima_server/pipeline/egress.py`: `Pacer` maintaining 1000ms lead buffer and WebSocket frame transmitter.
- **Providers & Security**:
  - `server/anima_server/providers/openai_compat.py`: OpenAI-compatible provider supporting Groq (`llama-3.3-70b-versatile`) with model validation and streaming.
  - `server/anima_server/tools/policy.py`: Enforces hardcoded `FORBIDDEN_ALWAYS` tools (reboot, firmware, wifi, token, factory reset), schema validation, and per-minute rate limits.
  - `server/anima_server/tools/registry.py`: Tool discovery, OpenAI function spec export, server tool execution, and device proxying via WebSocket.
- **Transport & Testing**:
  - `server/anima_server/transport/ws_server.py`: Bearer token authentication, protocol negotiation, and session management.
  - `server/anima_server/transport/session.py`: Session turn authority (Rule T1-T9), bounded queues, and reader pump.
  - `tools/fake_device.py`: Full simulated satellite with fault injection (dropped frames, jitter, late frames after barge-in, bad tokens).
  - 32 comprehensive tests across unit and integration scenarios (100% green).

### Tests
```sh
.venv/bin/python -m pytest server/tests -v   → 32 passed in 13.56s
.venv/bin/python -m pytest protocol/tests -v → 51 passed in 0.35s
```

### One-line demo command
```sh
PYTHONPATH=server .venv/bin/python -m pytest server/tests -v
```

---

## [Phase 0] 2026-10-29 — Skeleton and protocol package

### Added

- **Repository skeleton**: full directory layout per Architecture Plan section 3 — `protocol/`, `server/`, `firmware/`, `tools/`, `docs/`, `docs/decisions/`, `.github/workflows/`.
- **`protocol/constants.yaml`**: single source of truth for all wire-protocol constants (PROTO_VERSION=1, frame header layout, audio settings for uplink 16 kHz / downlink 24 kHz, timing, reconnect backoff, error codes, message type strings). R4 satisfied.
- **`protocol/schema.json`**: JSON Schema (draft-07) covering all 16 message types (hello, hello_ack, listen.start, listen.end, listen.stop, abort, stt, reply, tts.start, tts.stop, tool.call, tool.result, playback, telemetry, alert, error).
- **`protocol/vectors.json`**: 21 test vectors — 5 binary frames (uplink plain, FLAG_FIRST, FLAG_LAST, both flags, downlink) and 16 JSON messages (one of each type).
- **`protocol/gen.py`**: code generator. Reads `constants.yaml`, writes:
  - `server/anima_server/transport/protocol_gen.py` — Python constants, `AudioFrame` dataclass with `encode()` / `decode()`, error code and message type constants.
  - `firmware/main/net/protocol_gen.h` — C header with `#define` constants, `AnimaFrameHeader` packed struct, inline `anima_frame_encode()` / `anima_frame_decode()`. R6 satisfied.
- **`protocol/tests/test_vectors.py`**: 51 passing tests — regeneration, constants-vs-YAML agreement, all binary frame vectors, all JSON message vectors, encode→decode round-trips, error cases (too short, empty, unknown kind).
- **`docs/PROTOCOL.md`**: complete protocol reference (connection, handshake, binary frame layout, all JSON message types, error codes, keepalive, example sequences).
- **`docs/THIRD_PARTY.md`**: dependency and licence template (entries are placeholders; all deps must be pinned in Phase 1).
- **`docs/VERIFIED.md`**: verification log with Phase 0 entries (Python 3.14.4, pyyaml, pytest 9.2.0, struct module).
- **`docs/HANDOFF.md`**: handoff log with first entry (Phase 0 agent).
- **`docs/decisions/`**: directory for future decision records.
- **`CHANGELOG.md`**: this file.
- **`README.md`**: project overview.
- **`.gitignore`**: Python, C/C++, ESP-IDF patterns.
- **`server/pyproject.toml`**: project metadata, all Phase 1 runtime and dev dependencies listed (unversioned; pin in Phase 1).
- **`server/anima_server/__init__.py`**: empty package marker.
- **`server/.env.example`**: all env vars with comments, no real values.
- **`firmware/CMakeLists.txt`**, **`firmware/sdkconfig.defaults`**, **`firmware/sdkconfig.defaults.esp32s3`**, **`firmware/partitions.csv`** (from Architecture Plan section 7.3), **`firmware/main/CMakeLists.txt`**, **`firmware/main/idf_component.yml`**: stubs.
- **`firmware/host_test/CMakeLists.txt`**: stub for PC-side test builds.
- **`tools/fake_device.py`**: stub with full argument parser (implementation deferred to Phase 1).
- **`tools/ws_recorder.py`**: stub.
- **`tools/latency_report.py`**: stub.
- **`.github/workflows/ci.yml`**: CI — runs on push/PR, Python 3.11, installs pyyaml + pytest, runs `python protocol/gen.py` then `pytest protocol/tests`.

### Tests

```
python3 protocol/gen.py                    → Done. (self-check passes)
python3 -m pytest protocol/tests -v       → 51 passed in 0.09 s
```

### One-line demo command

```sh
python3 protocol/gen.py && python3 -m pytest protocol/tests -v
```
