# Third-Party Dependencies and Licenses

> **Template — fill in during Phase 1 before merging any dependency.**
> R13: Original code only. Every third-party dependency and its license goes into this file before it is merged.
> R14: Verify each library version against what is installed and record the verified call here.

---

## How to use this file

For every dependency added:
1. Record the package name, version range, and licence.
2. Note whether it is a runtime dependency or a development/test-only dependency.
3. Check the licence is compatible with the project's intended distribution.

---

## Runtime dependencies (server)

| Package | Version | Licence | Notes |
|---|---|---|---|
| `websockets` | 17.3 | BSD-3-Clause | WebSocket server and client. |
| `numpy` | 2.4.6 | BSD-3-Clause | PCM array operations, RMS, normalization. |
| `scipy` | 1.17.1 | BSD-3-Clause | Signal resampling for audio rates. |
| `opuslib` | 3.0.1 | BSD-3-Clause | Python bindings for libopus with PLC support. |
| `onnxruntime` | 1.31.1 | MIT | ONNX Runtime for CPU model execution. |
| `openai` | 3.41.0 | Apache-2.0 | Groq and OpenAI compatible streaming client. |
| `pydantic` | 2.14.1 | MIT | Configuration dataclasses and validation. |
| `jsonschema` | 4.26.0 | MIT | Tool argument schema validation. |
| `pyyaml` | 6.0.3 | MIT | Loads constants.yaml and tools.yaml. |
| `aiohttp` | 3.14.5 | Apache-2.0 | Async admin HTTP API. |

## Runtime dependencies (firmware)

| Component | Version | Licence | Notes |
|---|---|---|---|
| ESP-IDF | 5.x | Apache-2.0 | Device framework. Verify component versions. |
| esp-sr (WakeNet) | TBD | Espressif proprietary | Wake word. Stock phrase only in v1; confirm model licence for distribution. |
| esp_audio_codec | TBD | Apache-2.0 | Codec component. |
| esp_websocket_client | TBD | Apache-2.0 | WebSocket client. |
| cJSON | TBD | MIT | JSON parsing on device. |
| libopus | TBD | BSD-3-Clause | Opus codec. Check which ESP-IDF component bundles it. |

## AI model weights

| Model | Source | Licence | Notes |
|---|---|---|---|
| Whisper (base.en) | OpenAI via HuggingFace | MIT | Weights downloaded at runtime by faster-whisper. |
| Kokoro TTS | kokoro-onnx | Apache-2.0 | Confirm exact weight licence before distribution. |
| Silero VAD | Silero | MIT | ONNX checkpoint. |
| ESP-SR WakeNet | Espressif | Proprietary | On-device only, not redistributed as a file. |

## Development / test dependencies

| Package | Version | Licence | Notes |
|---|---|---|---|
| `pytest` | >=8.0 | MIT | Test runner. |
| `pytest-asyncio` | TBD | Apache-2.0 | Async test support. Add in Phase 1. |

---

## Licences to track before release

- ESP-SR WakeNet: confirm whether the model weights require a redistribution agreement with Espressif.
- Kokoro ONNX weights: confirm licence covers derivative works.
- Any model downloaded from HuggingFace: confirm the specific checkpoint licence matches the Hub metadata.

---

*Last updated: Phase 0 skeleton. All entries are placeholders; versions must be pinned and verified in Phase 1 (R14).*
