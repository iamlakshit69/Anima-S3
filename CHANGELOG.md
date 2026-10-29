# CHANGELOG

All notable changes to ANIMA-S3 are recorded here.
Format: `## [Phase N] YYYY-MM-DD — brief title` followed by a bullet list.

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
