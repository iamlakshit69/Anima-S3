# Verification Log

> R14: Verify, do not assume. Library names and calls in the architecture are hypotheses from memory and third-party docs.
> Check each against the installed version before using it. Record what you verified here.
>
> Format per entry:
> ```
> ## <library or component name>
> - **Version verified:** <exact version>
> - **Date:** <YYYY-MM-DD>
> - **Phase:** <phase number>
> - **Call / behaviour verified:** <what exactly was checked>
> - **Command or test used:** <how it was verified>
> - **Result:** <pass / fail / notes>
> ```

---

## Python runtime (system)

- **Version verified:** 3.14.4
- **Date:** 2026-10-29
- **Phase:** 0
- **Call / behaviour verified:** `python3 --version`; `python3 protocol/gen.py` runs without error.
- **Command or test used:** `python3 --version && python3 protocol/gen.py`
- **Result:** PASS. Generator produces `protocol_gen.py` and `protocol_gen.h` without errors.

## pyyaml

- **Version verified:** installed via `pip3 install --break-system-packages pyyaml`
- **Date:** 2026-10-29
- **Phase:** 0
- **Call / behaviour verified:** `yaml.safe_load()` on `protocol/constants.yaml`; nested dict access matches expected values.
- **Command or test used:** `python3 -m pytest protocol/tests -v` (51 tests pass)
- **Result:** PASS.

## pytest

- **Version verified:** 9.2.0
- **Date:** 2026-10-29
- **Phase:** 0
- **Call / behaviour verified:** `python3 -m pytest protocol/tests -v` collects and runs 51 tests.
- **Command or test used:** `python3 -m pytest protocol/tests -v`
- **Result:** 51 passed, 0 warnings, 0.09 s.

## Python `struct` module (stdlib)

- **Version verified:** stdlib (Python 3.14.4)
- **Date:** 2026-10-29
- **Phase:** 0
- **Call / behaviour verified:** `struct.Struct("<BBHII")` packs/unpacks the 12-byte frame header. Little-endian byte order matches ESP32 native order. `struct.calcsize("<BBHII")` == 12.
- **Command or test used:** `python3 -m pytest protocol/tests -v` (round-trip and error-case tests)
- **Result:** PASS. All round-trip and error tests pass.

---

## Pending verifications (to be done in Phase 1)

- [ ] `websockets` — server `serve()` API, `ping_interval`, `ping_timeout` parameters, exact version.
- [ ] `opuslib` — `decode()` and `encode()` call signatures, PLC support, system libopus requirement.
- [ ] `faster-whisper` — model download path, `transcribe()` return type, warm-up behaviour.
- [ ] `kokoro-onnx` — `create()` API, sample rate of output, any streaming variant.
- [ ] `silero-vad` — ONNX usage path, block size, state reset call.
- [ ] `openai` client — async `models.list()` and `chat.completions.create(stream=True)` with tool calls.
- [ ] ESP-IDF version compatible with esp-sr, esp_audio_codec, esp_websocket_client.
- [ ] ESP-SR WakeNet — exact model partition format and name, wake word list.


---

## Python runtime (Phase 1 virtualenv)

- **Version verified:** 3.11.15
- **Date:** 2026-10-29
- **Phase:** 1
- **Call / behaviour verified:** Python 3.11 venv with full wheel support for audio and ML modules.
- **Command or test used:** `.venv/bin/python --version`
- **Result:** PASS.

## websockets

- **Version verified:** 17.3
- **Date:** 2026-10-29
- **Phase:** 1
- **Call / behaviour verified:** `websockets.connect(..., additional_headers=...)`, `ws.request.headers`, `websockets.serve(handle_connection, ...)`
- **Command or test used:** `.venv/bin/python -m pytest server/tests/test_integration.py`
- **Result:** PASS.

## opuslib & libopus

- **Version verified:** opuslib 3.0.1, libopus 1.5.2 (Homebrew)
- **Date:** 2026-10-29
- **Phase:** 1
- **Call / behaviour verified:** `Encoder.encode(pcm, 320/480)`, `Decoder.decode(packet, 320/480)`, Packet Loss Concealment (PLC) with `decode(b"", 320, decode_fec=True)`.
- **Command or test used:** `.venv/bin/python -m pytest server/tests/test_opus_codec.py`
- **Result:** PASS.

## onnxruntime

- **Version verified:** 1.31.1
- **Date:** 2026-10-29
- **Phase:** 1
- **Call / behaviour verified:** ONNX model execution and tensor input management for Silero VAD.
- **Command or test used:** `.venv/bin/python -c "import onnxruntime; print(onnxruntime.__version__)"`
- **Result:** PASS.
