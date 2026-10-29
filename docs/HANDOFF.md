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

### Next agent: start here
- Start **Phase 1: Server with fake device**.
- Review Architecture Plan section 6 (Server design) and section 9 (Testing strategy).
- Server configuration will use Groq (`llama-3.3-70b-versatile`) and CPU inference for Whisper (`base.en int8`) and Kokoro TTS.

