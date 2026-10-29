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
| `websockets` | TBD | BSD-3-Clause | WebSocket server. Verify API in Phase 1. |
| `numpy` | TBD | BSD-3-Clause | PCM array operations. |
| `scipy` | TBD | BSD-3-Clause | `resample_poly` for rate conversion. |
| `faster-whisper` | TBD | MIT | STT. Wraps CTranslate2 and Whisper weights. |
| `kokoro-onnx` | TBD | Apache-2.0 | TTS. Uses ONNX Runtime. Verify `create` API. |
| `silero-vad` | TBD | MIT | VAD. Use ONNX path to avoid PyTorch. |
| `openai` | TBD | Apache-2.0 | OpenAI-compatible client for Groq/Ollama/OpenAI. |
| `opuslib` | TBD | BSD-3-Clause | Python bindings for libopus. Requires system libopus. |
| `pydantic` | TBD | MIT | Message model validation. |
| `jsonschema` | TBD | MIT | Validates tool argument schemas. |
| `pyyaml` | TBD | MIT | Loads constants.yaml. |
| `aiohttp` | TBD | Apache-2.0 | Admin HTTP API. |

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
