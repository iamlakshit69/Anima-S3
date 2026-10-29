# ANIMA-S3

A voice assistant in two parts:

- **Satellite** — ESP32-S3 firmware (ESP-IDF 5.x, C++). Wake word, I2S audio, Opus codec, WebSocket client, small allowlist of hardware tools, LED and optional LCD, A/B OTA.
- **Server** — Python 3.11+ asyncio service. Voice activity detection and endpointing, faster-whisper STT, pluggable LLM (Groq / Ollama / OpenAI), Kokoro TTS, tool orchestration, diagnostics.

One WebSocket carries Opus audio (binary frames, 12-byte header) and JSON control messages. Every message and audio frame carries a `turn` id that drives stale-work cancellation throughout the pipeline.

## Project status

| Phase | Description | Status |
|---|---|---|
| **0** | Skeleton, protocol package, CI | ✅ Done |
| **1** | Server with fake device | 🔲 Pending |
| **2** | Firmware audio loop (push-to-talk, LED) | 🔲 Pending |
| **3** | Wake word, full state machine, reconnect | 🔲 Pending |
| **4** | Tools, fast-path intents, endpoint tuning | 🔲 Pending |
| **5** | Provisioning, settings, OTA, admin API | 🔲 Pending |
| **6** | LCD UI, emotion, semantic endpointing | 🔲 Pending |
| **7** | Hardening, soak, packaging | 🔲 Pending |

## Quick start (Phase 0)

```sh
# Regenerate protocol code from constants.yaml
python3 protocol/gen.py

# Run protocol tests
python3 -m pytest protocol/tests -v
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full design document (authoritative)
- [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — wire protocol reference
- [`docs/VERIFIED.md`](docs/VERIFIED.md) — verified library versions and API calls
- [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md) — dependencies and licences
- [`docs/HANDOFF.md`](docs/HANDOFF.md) — agent handoff log
- [`AGENTS.md`](AGENTS.md) — operating manual for agents and humans

## Repository layout

```
anima-s3/
├── protocol/          schema.json, constants.yaml, vectors.json, gen.py, tests/
├── server/            Python server (anima_server/, tests/, pyproject.toml)
├── firmware/          ESP-IDF project (main/, host_test/, partitions.csv)
├── tools/             fake_device.py, ws_recorder.py, latency_report.py
└── docs/              ARCHITECTURE, PROTOCOL, HARDWARE, THIRD_PARTY, VERIFIED, decisions/, HANDOFF
```

## Design principles

- **One place per constant** — `protocol/constants.yaml` → generated to Python and C. No magic numbers.
- **Generated files are not edited by hand** — change `protocol/constants.yaml` and run `protocol/gen.py`.
- **Turn model** — every audio frame and turn-scoped message carries a `turn` id. Stale items are dropped at every stage.
- **Half-duplex** — microphone is muted while the device speaks. No AEC required.
- **Original code only** — no copy-paste from other projects; ideas only.
