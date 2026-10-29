# HANDOFF LOG

This file records what each agent or work session did, what is half-done, what is blocked, and what the next agent should do first.

Format per entry:

```
## Entry NNN — <Date> — <Author/Agent>
### Done
### Half-done or in progress
### Blocked on
### Next agent: start here
```

---

## Entry 001 — 2026-10-29 — Phase 0 agent

### Done

- Created full repository skeleton per Architecture Plan.md section 3.
- `protocol/constants.yaml` — single source of truth for all wire-protocol constants (PROTO_VERSION, frame layout, audio settings, timing, reconnect backoff, error codes, message types).
- `protocol/schema.json` — JSON Schema (draft-07) for all 16 message types.
- `protocol/vectors.json` — 21 test vectors: 5 binary frames (uplink plain, first, last, first+last, downlink), 16 JSON messages (one of each type).
- `protocol/gen.py` — code generator. Reads `constants.yaml`, writes `server/anima_server/transport/protocol_gen.py` (Python dataclass + struct codec) and `firmware/main/net/protocol_gen.h` (C header with #define constants, AnimaFrameHeader struct, inline encode/decode helpers). Runs self-check after generation.
- `server/anima_server/transport/protocol_gen.py` — generated (do not edit).
- `firmware/main/net/protocol_gen.h` — generated (do not edit).
- `protocol/tests/test_vectors.py` — 51 tests: regenerate, constants match YAML, all vectors round-trip, encode/decode, error cases.
- `docs/PROTOCOL.md` — complete protocol reference from Architecture Plan section 4.
- `docs/THIRD_PARTY.md` — dependency and licence template (all entries are placeholders for Phase 1).
- `docs/VERIFIED.md` — verification log with Phase 0 entries (Python, pyyaml, pytest, struct).
- `docs/HANDOFF.md` — this file (first entry).
- `docs/decisions/` — directory created, empty.
- `CHANGELOG.md` — Phase 0 entry.
- `README.md` — project overview.
- `.gitignore` — Python, C/C++, ESP-IDF patterns.
- `server/pyproject.toml` — project metadata and all Phase 1 dependencies listed.
- `server/anima_server/__init__.py` — empty package marker.
- `server/.env.example` — all env vars with comments, no real values.
- `firmware/CMakeLists.txt`, `firmware/sdkconfig.defaults`, `firmware/sdkconfig.defaults.esp32s3`, `firmware/partitions.csv`, `firmware/main/CMakeLists.txt`, `firmware/main/idf_component.yml` — stubs.
- `firmware/host_test/CMakeLists.txt` — stub for PC-side test builds.
- `tools/fake_device.py`, `tools/ws_recorder.py`, `tools/latency_report.py` — stubs with argument parsers.
- `.github/workflows/ci.yml` — CI workflow (push + PR, Python 3.11, pytest).

### Tests run

```
python3 protocol/gen.py       → Done. (0 errors)
python3 -m pytest protocol/tests -v  → 51 passed in 0.09s
```

### Half-done or in progress

- Nothing. Phase 0 deliverables are complete.

### Blocked on

- Nothing in Phase 0.
- Phase 1 requires answers to open items O3 (LLM model) and O6 (server hardware) before the full server can be validated (see Architecture Plan section 1.4 and AGENTS.md section 0).

## Entry 002 — 2026-10-29 — Phase 0 Completion & Hardware Kickoff

### Done
- Owner answered all open questions O1 through O6:
  - O1: ESP32-S3-WROOM-1 / N16R8 (16MB Flash, 8MB Octal PSRAM), INMP441 mic, MAX98357A amplifier.
  - O2: Cloud-hosted server (VPS/VM), ESP32 connects over internet via `wss://`.
  - O3: Groq — `llama-3.3-70b-versatile`.
  - O4: "Hey Anima" (custom phrase, Phase 3 blocker; fallback to stock word/PTT in Phase 2).
  - O5: LCD is Phase 6 only (omitted for v1).
  - O6: Cloud VM, CPU only (x86).
- Created `docs/HARDWARE.md` with verified component models, pinouts (avoiding GPIO 26-37 for Octal PSRAM), and pre-flash checklist.
- Added Decision Record `docs/decisions/001-cloud-vps-and-wss.md` for internet-accessible cloud server and `wss://` requirement.
- Added `server/tools.yaml` with safe/forbidden tools and rate limits.
- Added `firmware/partitions.csv`, `firmware/sdkconfig.defaults`, `firmware/sdkconfig.defaults.esp32s3`, `firmware/main/CMakeLists.txt`, `firmware/main/idf_component.yml`.
- Implemented and verified `firmware/host_test/test_protocol_host.cc` with CMake / ctest.
- Implemented tool CLI stubs: `tools/fake_device.py`, `tools/ws_recorder.py`, `tools/latency_report.py`.
- Configured `.github/workflows/ci.yml` with both Python protocol tests and C++ host tests.
- Status board in `AGENTS.md` and `Notes for agents.md` updated: Phase 0 is checked off!

### Tests run
```
python3 protocol/gen.py                                                    -> 0 errors
python3 -m pytest protocol/tests -v                                        -> 51 passed in 0.08s
cmake -S firmware/host_test -B firmware/host_test/build && ctest ...        -> 100% tests passed (1/1)
```

### Half-done or in progress
- None. Phase 0 is 100% complete and accepted.

### Blocked on
- None. Ready for Phase 1.

## Entry 003 — 2026-10-29 — Phase 1 Completion (Server with Fake Device)

### Done
- Implemented complete server package (`server/anima_server`):
  - `config.py`: typed configuration with validation invariants.
  - `core/turn.py`: `TurnScope` managing task tracking and cancellation per turn (Rule T6).
  - `core/sentinel.py`, `core/retry.py`, `core/metrics.py`, `core/supervisor.py`, `core/logger.py`.
  - `audio/opus_codec.py`: `OpusDecoder` with Packet Loss Concealment (PLC) and `OpusEncoder` with re-chunking.
  - `audio/rechunk.py`: 512-sample block re-chunker for VAD.
  - `audio/vad.py`: `SileroVAD` and deterministic `FakeVAD`.
  - `audio/endpointer.py`: `Endpointer` state machine with `FixedPolicy`, hysteresis, and PTT `force_end`.
  - `audio/dsp.py`: peak normalization, RMS, trailing silence trimming, hallucination filter.
  - `pipeline/ingest.py`: uplink frame decode and endpoint dispatch.
  - `pipeline/stt.py`: Whisper STT stage with audio length verification.
  - `pipeline/llm.py`: history management, streaming tokens, fallback apology, and tool execution loop.
  - `pipeline/tts.py`: token accumulator with early first-phrase release and speech synthesizer.
  - `pipeline/egress.py`: frame `Pacer` (1000ms lead buffer) and Opus frame downlink transmitter.
  - `pipeline/intents.py`: fast-path intents stub.
  - `providers/base.py` & `providers/openai_compat.py`: OpenAI/Groq compatible client.
  - `tools/policy.py`: enforces hardcoded `FORBIDDEN_ALWAYS` tools, JSON schema checks, rate limits.
  - `tools/registry.py`: tool registry, schema conversion, and WebSocket device proxy.
  - `transport/protocol.py`, `transport/session.py`, `transport/ws_server.py`, `main.py`.
  - `tools/fake_device.py`: simulated satellite with fault injection (scenarios: `normal`, `barge_in`, `no_speech`, `bad_token`, `reconnect`).
- Implemented full test suite in `server/tests/` (32 tests):
  - `test_config.py`, `test_turn_rules.py`, `test_endpointer.py`, `test_opus_codec.py`, `test_pacer.py`, `test_supervisor.py`, `test_tool_policy.py`, `test_device_proxy.py`, `test_integration.py`.
- All 83 tests (32 server tests + 51 protocol tests) passing.

### Tests run
```sh
.venv/bin/python -m pytest server/tests -v   → 32 passed in 13.56s
.venv/bin/python -m pytest protocol/tests -v → 51 passed in 0.35s
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 100% passed
```

### Half-done or in progress
- None. Phase 1 is 100% complete and accepted.

### Blocked on
- None. Ready for Phase 2.

## Entry 004 — 2026-10-29 — Phase 2 Completion (Firmware Audio Loop, PTT, LED UI, Host Tests)

### Done
- Implemented complete C++ firmware package for ESP32-S3:
  - `config.h`: single source of truth for firmware constants.
  - `boards/breadboard_s3/pins.h` & `boards/board.h`: hardware abstraction matching `docs/HARDWARE.md` (INMP441 on GPIO 4,5,6; MAX98357A on GPIO 7,15,16; BOOT GPIO 0; PTT GPIO 47; Status LED GPIO 48; avoiding reserved Octal PSRAM GPIO 26-37).
  - `audio/ring_buffer.h`: lock-free SPSC circular ring buffer supporting pre-roll discard and zero dynamic heap allocations in audio loops.
  - `audio/jitter_buffer.h`/`.cc`: 24 kHz playback buffer with 200ms prebuffer threshold, underrun detection, and barge-in clear.
  - `audio/audio_io.h`/`.cc`: I2S driver for INMP441 RX (16 kHz, 32-bit slot conversion to 16-bit) and MAX98357A TX (24 kHz standard Philips), half-duplex mic muting, and speaker DMA zeroing.
  - `audio/opus_enc.h`/`.cc` & `audio/opus_dec.h`/`.cc`: 16 kHz VOIP Opus encoder and 24 kHz Opus decoder.
  - `audio/cues.h`/`.cc`: synthesized audio chimes (wake chime, ready, error).
  - `sys/buttons.h`/`.cc`: debounced button handler for PTT (down/up) and BOOT (tap barge-in vs long-press provisioning).
  - `app/events.h` & `app/state_machine.h`/`.cc`: table-driven transition engine with 21 transitions covering boot, wifi/ws reconnect, PTT turns, barge-in interrupts, and unhandled event rejection.
  - `ui/ui.h` & `ui/led_ui.cc`: LED pattern generator (IDLE off, LISTENING solid on, THINKING slow blink, SPEAKING fast pulse, PROVISIONING double blink).
  - `sys/diag.h`/`.cc`: self-test mode, free heap/PSRAM reporting, and microphone audio analysis (clipping & dead mic detection).
  - `net/ws_client.h`/`.cc`: WebSocket transport with exponential backoff & 20% jitter.
  - `app/app.h`/`.cc` & `main.cc`: application coordinator and FreeRTOS task integration.
- Expanded C++ Host Test suite in `firmware/host_test/` (all 6 suites passing):
  - `test_protocol_host`: wire framing and header decode.
  - `test_ring_buffer_host`: SPSC circular wraparound, overflow, underflow, pre-roll trim.
  - `test_jitter_buffer_host`: 200ms prebuffer threshold, underruns, barge-in clear.
  - `test_buttons_host`: PTT down/up debounce, short tap, >3s long press.
  - `test_state_machine_host`: all 21 table-driven transitions, barge-in, unhandled event rejection.
  - `test_diag_host`: microphone clipping detection, silence detection, memory metrics.
- Updated status board in `AGENTS.md` and `Notes for agents.md`: Phase 2 checked off.

### Tests run
```sh
cmake -S firmware/host_test -B firmware/host_test/build && ctest ... → 6 passed in 0.01s (100%)
.venv/bin/python -m pytest server/tests -v                           → 32 passed in 13.67s (100%)
.venv/bin/python -m pytest protocol/tests -v                         → 51 passed in 0.07s (100%)
```

### Half-done or in progress
- None. Phase 2 deliverables are 100% complete and accepted.

### Blocked on
- None. Ready for Phase 3.

### Next agent: start here
- Start **Phase 3: Wake word, full state machine, reconnect drills**.
- Review Architecture Plan section 7.10 (Wake word and front end) and section 11 (Phase 3 acceptance).
- Deliverables for Phase 3:
  - ESP-SR integration & model partition loading (`wake_word.h` / `wake_word.cc`)
  - Integration of wake word model in `partitions.csv` (`model` partition at 0x620000, 4MB)
  - Full state machine integration with reconnect drills (server-kill and router-off simulations)
  - Measure false wake counts and test PTT fallback when wake word is disabled



