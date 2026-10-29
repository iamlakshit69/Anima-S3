# ANIMA-S3: ESP32 Voice Satellite + ANIMA Server

*Architecture plan for a coding agent · Draft v1 · 29 October 2026*

## 0. How to use this document

Audience: a coding agent and the human reviewing its work. This plan defines what to build, in what order, and through which interfaces. It contains pseudocode, not final code.

Rules for the agent:

1. Build in the phases of section 11. Do not start a phase until the previous phase's acceptance tests pass.
2. Verify every library API against the installed version before using it. Library names and calls in this plan come from memory and third-party docs, so treat them as hypotheses.
3. Write original code from this spec. Do not copy code from xiaozhi-esp32, Willow, Harvya or any other project; take ideas only. Record every third-party dependency and its license in docs/THIRD\_PARTY.md.
4. Never invent hardware facts. Pin numbers in section 8 are defaults taken from an unverified summary. Confirm them against the real wiring before flashing.
5. Keep each constant in exactly one place: protocol/constants.yaml, server/config.py, firmware/main/config.h. No magic numbers elsewhere.
6. Every stage that waits (queue get, network call, model inference) must re-check turn staleness after the wait (section 5).
7. Ask the human before deviating from a locked decision (section 1.3).
8. Each phase ends with: tests green, a CHANGELOG entry, and a one-line demo command.

## 1. Product definition

### 1.1 What we are building

A voice assistant in two parts.

- **Satellite (ESP32-S3):** microphone, speaker amp, optional LCD, buttons. It detects the wake word, streams audio to the server, plays the reply, shows state, and runs a small allowlist of hardware tools (volume, brightness, lamp).
- **Server (Python, derived from ANIMA):** voice activity detection and endpointing, speech-to-text, LLM, text-to-speech, tool orchestration, diagnostics.

The device is a thin client. All intelligence lives on the server.

### 1.2 Goals and non-goals

Goals:

- G1: time from end of user speech to first audible reply is 1.5 s or less at p50 and 2.5 s or less at p95, on a home LAN with a cloud LLM.
- G2: barge-in (button press during a reply) silences the speaker within 200 ms.
- G3: the system recovers by itself from Wi-Fi drops, server restarts and LLM API outages. No power cycling.
- G4: no microphone audio leaves the device before the wake word or a button press.
- G5: every turn logs a latency breakdown, and a diagnostics command produces a health report.
- G6: everything except hardware drivers is testable without hardware, through a fake device.

Non-goals for v1: acoustic echo cancellation or full duplex, more than two simultaneous devices, server-initiated speech, camera, internet exposure (the design allows it later), on-device STT or LLM, MQTT or UDP transport.

### 1.3 Locked decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Device framework | ESP-IDF 5.x, C++ | ESP-SR wake word and audio front end need it; full PSRAM control |
| Server runtime | Python 3.11+, asyncio | Reuses ANIMA's design and tests |
| Transport | One WebSocket (ws:// now, wss:// ready) | One connection carries audio and control |
| Audio codec | Opus both ways. Uplink 16 kHz mono, 20 ms frames. Downlink 24 kHz mono, 20 ms frames | Kokoro outputs 24 kHz; Whisper wants 16 kHz |
| Echo handling | Half-duplex: mic muted while the device speaks | No speaker reference signal, so AEC is not reliable |
| Turn IDs | Device-authoritative u32, carried on every message and audio frame | Prevents stale audio and text from speaking over a new turn |
| Endpointing | Server-side. Device ends a turn only on push-to-talk release | Larger models and adaptive logic live on the server |
| STT | faster-whisper, local, int8 | Existing ANIMA stage |
| LLM | Provider interface. Groq default, Ollama optional | Not tied to one vendor |
| TTS | Kokoro ONNX, local | Existing ANIMA stage |
| Wake word | ESP-SR WakeNet stock word first; push-to-talk always available | Custom words need extra work |
| Tools | Allowlist with risk classes. No reboot or firmware tools for the LLM | A compromised server or prompt must not be able to reflash the device |
| OTA | A/B partitions with rollback, offered by an authenticated server manifest | Safe field updates |

### 1.4 Open items to confirm with the human before Phase 2

- O1: exact board, microphone and amplifier.
- O2: LAN only, or reachable from the internet.
- O3: LLM provider and model name (the server validates this at startup, section 6).
- O4: wake word phrase.
- O5: is the LCD part of v1.
- O6: what hardware does the server run on (CPU only, or GPU).

## 2. System architecture

```
 ESP32-S3 satellite                                   Server (Python, asyncio)
┌───────────────────────────────┐   one WebSocket   ┌─────────────────────────────────────┐
│ mic (I2S) → ring → wake word  │  ───────────────► │ ws_server → session                 │
│        └→ Opus enc (16 kHz)   │   Opus + JSON     │  ingest: Opus dec → VAD/endpointer  │
│ Opus dec (24 kHz) → jitter buf│  ◄─────────────── │  stt: faster-whisper                │
│        → I2S amp              │   turn id on all  │  llm: provider + tools + history    │
│ state machine, tools, UI, OTA │                   │  tts: Kokoro → Opus enc → pacer     │
└───────────────────────────────┘                   │  supervisor, metrics, diagnostics   │
                                                    └─────────────────────────────────────┘
```

### 2.1 Responsibilities

| Concern | Device | Server |
| --- | --- | --- |
| Wake word | Yes (offline) | No |
| Noise suppression, gain | Optional, ESP-SR front end | Normalise before STT |
| Voice activity and end of utterance | No (except push-to-talk release) | Yes |
| Speech to text | No | Yes |
| LLM and conversation history | No | Yes |
| Text to speech | No | Yes |
| Opus encode and decode | Encode 16 kHz, decode 24 kHz | Decode 16 kHz, encode 24 kHz |
| Playback buffering | Jitter buffer, about 1 s | Paces frames so the buffer never overflows |
| Tool execution | Device tools (allowlist) | Server tools, plus proxy to device tools |
| Turn authority | Increments the turn ID | Obeys it, drops stale work |
| State display (LED, LCD) | Yes | Sends state hints (stt, reply text, emotion) |
| Firmware updates | Downloads and verifies | Publishes manifest |

### 2.2 One turn, end to end

1. Device is IDLE with the wake word armed. Audio stays on the device.
2. Wake word fires (or button pressed). Device increments `turn`, enters LISTENING, plays a short cue, sends `listen.start`.
3. Device streams Opus frames tagged with `turn`, starting with a few hundred ms of buffered pre-roll.
4. Server decodes, runs VAD and the endpointer, and buffers PCM for the turn.
5. Endpointer decides the user has finished. Server sends `listen.stop`. Device stops streaming and shows THINKING.
6. STT transcribes. Server sends `stt` (for the subtitle). Fast-path intents run first (section 6.9); otherwise the LLM stage runs.
7. LLM streams tokens. Server may issue `tool.call` to the device and wait for `tool.result`.
8. The TTS accumulator groups tokens into phrases. Kokoro synthesises each phrase.
9. Server sends `tts.start`, then Opus frames paced about 1 s ahead of real time, then `tts.stop`. Each sentence's text goes out as a `reply` message when its first frame is queued.
10. Device decodes into the jitter buffer and plays. Mic is muted from `tts.start` until playback ends plus a short tail.
11. Device returns to IDLE, or to LISTENING if the server asked for a follow-up turn.

### 2.3 Latency budget (targets, after end of speech)

| Stage | Target |
| --- | --- |
| Endpoint decision (adaptive silence) | 0.4 to 0.7 s |
| STT (base.en int8, short utterance) | 0.2 to 0.4 s |
| LLM first token (cloud) | 0.3 to 0.5 s |
| TTS first phrase | 0.3 to 0.5 s |
| Network, decode, buffer start | under 0.1 s |
| Total | about 1.3 to 2.0 s |

The fixed 1.1 s silence timer in the current ANIMA is the largest avoidable cost. Section 6.4 replaces it.

## 3. Repository layout (top level)

```
anima-s3/
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── ARCHITECTURE.md        # this plan
│   ├── PROTOCOL.md            # section 4, kept in sync with protocol/
│   ├── HARDWARE.md            # verified pinout, wiring, bill of materials
│   └── THIRD_PARTY.md         # dependencies and licenses
├── protocol/                  # single source of truth for the wire format
│   ├── schema.json            # JSON Schema for every message
│   ├── constants.yaml         # audio rates, frame sizes, kinds, flags, error codes
│   └── gen.py                 # generates server/anima_server/transport/protocol_gen.py
│                              #   and firmware/main/net/protocol_gen.h
├── server/                    # detailed in section 6
├── firmware/                  # detailed in section 7
└── tools/
    ├── fake_device.py         # simulated ESP32 (section 9)
    ├── ws_recorder.py         # records a session to disk for replay
    └── latency_report.py      # summarises logs into a table
```

## 4. Wire protocol v1

### 4.1 Connection and handshake

- Device connects to `ws://<host>:<port>/v1/device`. Host comes from NVS settings, with mDNS (`anima.local`) as fallback.
- HTTP upgrade carries `Authorization: Bearer <device_token>` and `X-Device-Id`. Server closes with code 4401 if the token is wrong.
- First message from the device must be `hello` within 5 s. Server replies `hello_ack`. If `proto` is not supported, server sends `error` with `E_PROTO_VERSION` and closes.
- Binary frames are audio. Text frames are JSON objects with a `type` field. Example on the wire: `{"type":"listen.start","turn":7,"reason":"wake_word"}`.

### 4.2 Binary audio frame

Little-endian (ESP32 native). One WebSocket binary message holds exactly one Opus packet, so the payload length is the WebSocket frame length minus 12.

```
offset size type   field
0      1    u8     kind     0x01 audio uplink (device to server), 0x02 audio downlink
1      1    u8     flags    bit0 FIRST frame of the turn stream, bit1 LAST frame
2      2    u16    seq      per-direction frame counter, wraps
4      4    u32    turn     turn id
8      4    u32    t_ms     sender timestamp in ms since the start of this stream
12     n    bytes  opus     one Opus packet (20 ms)
```

Uplink Opus settings: 16 kHz, mono, 20 ms, application VOIP, 16 to 24 kbps. Downlink: 24 kHz, mono, 20 ms, 24 to 32 kbps. The `hello` message states the settings, so both sides can verify them.

### 4.3 JSON messages

Schema notation below. `?` means optional. Every message that belongs to a turn carries `turn`.

Device to server:

```
hello        { proto:int, device_id:str, fw:str, board:str, features:[str],
               audio:{up:{codec,rate,frame_ms}, down:{codec,rate,frame_ms}},
               tools:[ToolSpec], last_turn:int }
listen.start { turn:int, reason:'wake_word'|'button'|'barge_in', wake_word?:str }
listen.end   { turn }                   # push-to-talk release only
abort        { turn }                   # stop speaking, do not start a new turn
tool.result  { turn, id:str, ok:bool, result?:any, error?:str }
playback     { turn, event:'started'|'finished'|'underrun'|'flushed', buffered_ms:int }
telemetry    { state:str, rssi:int, heap_free:int, psram_free:int, uptime_s:int, battery?:int }

ToolSpec     { name:str, description:str, params:JSONSchema, risk:'safe'|'confirm' }
```

Server to device:

```
hello_ack    { proto:int, session_id:str, server:str, listen_timeout_ms:int,
               max_turn_ms:int, ota?:OtaOffer }
listen.stop  { turn, reason:'endpoint'|'no_speech'|'max_len'|'error' }
stt          { turn, text:str }
reply        { turn, text:str, emotion?:str }     # one per spoken sentence, for subtitles
tts.start    { turn }
tts.stop     { turn, reason:'done'|'aborted'|'error' }
tool.call    { turn, id:str, name:str, args:object, timeout_ms:int }
alert        { level:'info'|'warn'|'error', code:str, text:str }
error        { code:str, text:str, fatal:bool }

OtaOffer     { version:str, url:str, sha256:str, size:int }
```

### 4.4 Error codes

| Code | Meaning | Device behaviour |
| --- | --- | --- |
| E\_PROTO\_VERSION | Unsupported protocol version | Show error, retry with backoff |
| E\_AUTH | Bad or missing token | Show error, stop retrying until reconfigured |
| E\_BAD\_FRAME | Malformed binary frame | Log, continue |
| E\_STT\_FAIL | Transcription failed | Play error chime, return to IDLE |
| E\_LLM\_FAIL | LLM unreachable after retries | Server speaks a fallback apology |
| E\_TTS\_FAIL | Synthesis failed | Server plays an error tone |
| E\_TOOL\_DENIED | Tool not in allowlist or policy refused | Reported to LLM as a tool error |
| E\_TOOL\_TIMEOUT | Device did not answer in time | Reported to LLM as a tool error |
| E\_BUSY | Server at session capacity | Retry with backoff |
| E\_INTERNAL | Unexpected server fault | Return to IDLE |

### 4.5 Keepalive and reconnect

- Device sends a WebSocket ping every 10 s. Server closes the connection after 30 s of silence.
- Device reconnects with exponential backoff and jitter: 1 s, 2 s, 4 s, up to 30 s. It sends a new `hello` with `last_turn`, and the server starts a fresh session. Any turn in progress is abandoned.
- Server restarts must not require touching the device.

### 4.6 Example sequences

A. Normal turn

```
D  listen.start(turn=7, wake_word)      D  audio frames turn=7 ...
S  listen.stop(7, endpoint)             S  stt(7, text)
S  tts.start(7)                         S  audio frames turn=7 ... LAST
S  reply(7, sentence)                   S  tts.stop(7, done)
D  playback(7, finished)                D  state IDLE
```

B. Barge-in

```
D  (SPEAKING turn=7) button pressed: flush playback, turn=8
D  listen.start(turn=8, barge_in)       D  audio frames turn=8 ...
S  sees 8 > 7: cancels turn 7 tasks, drops queued turn 7 work
   late turn 7 frames and messages are dropped on both sides
```

C. Tool call

```
S  tool.call(7, id=a1, name=set_volume, args={level:40}, timeout_ms=2000)
D  policy check, execute            D  tool.result(7, a1, ok=true)
S  feeds the result to the LLM and continues the reply
```

D. No speech

```
D  listen.start(turn=9)                 S  no speech within listen_timeout_ms
S  listen.stop(9, no_speech)            D  state IDLE
```

## 5. Turn model and concurrency rules

A turn is one user utterance plus the assistant's reply. This is the most important correctness mechanism in the system. It generalises ANIMA's generation IDs across a network.

### 5.1 Rules

- **T1.** The device increments `turn` (u32) at every `listen.start`, including barge-in. After boot, the next turn is `last_turn + 1`, where `last_turn` is kept in RAM and sent in `hello`.
- **T2.** Every audio frame and every turn-scoped JSON message carries `turn`.
- **T3.** The server session keeps `current_turn`. On `listen.start` with a higher turn: cancel everything bound to older turns, clear per-turn buffers, then start the new turn. A turn that is equal or lower is ignored and counted in metrics.
- **T4.** Every queue item is tagged `(turn, payload)`. A consumer drops any item whose turn is not the session's current turn.
- **T5.** Check staleness before and after every await that can take more than a few ms: queue get, model inference, network call, sleep.
- **T6.** Long operations (LLM stream, TTS synthesis, tool wait) are bound to a `TurnScope` and must stop when it is cancelled. Cancelling must release resources, for example by closing the HTTP stream.
- **T7.** The device applies the same rule downlink: drop frames and messages whose turn is lower than its own current turn. On barge-in, flush the decode queue, jitter buffer and I2S DMA before sending `listen.start`.
- **T8.** End markers (`tts.stop`, LAST flag, END\_OF\_SPEECH) count only if their turn is current.
- **T9.** Not turn-scoped: `hello`, `hello_ack`, `alert`, `error`, `telemetry`.

### 5.2 TurnScope and session turn handling

```python
class TurnScope:
    def __init__(self, turn):
        self.turn = turn
        self.cancelled = asyncio.Event()
        self.tasks = set()

    def spawn(self, coro):
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
        return t

    def cancel(self):
        self.cancelled.set()
        for t in list(self.tasks):
            t.cancel()

class Session:
    def begin_turn(self, turn, reason):
        if turn <= self.current_turn:
            self.metrics.stale_listen_start += 1
            return
        if self.scope:
            self.scope.cancel()
        self.current_turn = turn
        self.scope = TurnScope(turn)
        self.drain_all_queues()
        self.endpointer = Endpointer(self.cfg, self.models.vad, self.policy)
        self.latency = TurnLatency(turn=turn, listen_start=now())
        self.state = LISTENING

    def is_stale(self, turn):
        return turn != self.current_turn
```

Refactor note: ANIMA keeps its queues, `turn_controller` and `playback_state` as module-level globals. In this server they become fields of `Session`, so tests construct a fresh session instead of calling reset helpers.

## 6. Server design

### 6.1 Directory layout

```
server/
├── pyproject.toml
├── .env.example
├── tools.yaml                       # tool allowlist and limits (section 6.10)
├── anima_server/
│   ├── main.py                      # entry: config, models, provider check, serve
│   ├── config.py                    # Config dataclass, env loading, validate()
│   ├── models.py                    # ModelHub: Whisper, Kokoro, Silero (load once, warm up)
│   ├── core/
│   │   ├── turn.py                  # TurnScope
│   │   ├── sentinel.py              # END_OF_RESPONSE, END_OF_SPEECH
│   │   ├── retry.py                 # retry_with_backoff, generate_error_tone (port from ANIMA)
│   │   ├── supervisor.py            # per-session stage supervision
│   │   ├── metrics.py               # TurnLatency, counters, latency log line
│   │   └── logger.py                # port from ANIMA
│   ├── transport/
│   │   ├── ws_server.py             # accept, auth, handshake
│   │   ├── session.py               # Session: queues, state, reader loop
│   │   ├── protocol.py              # frame codec, message models
│   │   └── protocol_gen.py          # generated from /protocol (do not edit)
│   ├── audio/
│   │   ├── opus_codec.py            # decoder with PLC, encoder with re-chunking
│   │   ├── rechunk.py               # fixed-size block re-chunker
│   │   ├── vad.py                   # Silero wrapper with hysteresis thresholds
│   │   ├── endpointer.py            # utterance state machine + EndOfTurnPolicy
│   │   └── dsp.py                   # normalize, trim_trailing_silence, hallucination filter
│   ├── pipeline/
│   │   ├── ingest.py                # uplink frames to endpointer to stt queue
│   │   ├── stt.py
│   │   ├── intents.py               # fast-path commands that skip the LLM
│   │   ├── llm.py                   # history, tool loop, fallback
│   │   ├── tts.py                   # accumulator + synthesizer
│   │   └── egress.py                # PCM to Opus to pacer to WebSocket
│   ├── providers/
│   │   ├── base.py                  # LLMProvider protocol, event types
│   │   └── openai_compat.py         # Groq, Ollama, OpenAI via base_url
│   ├── tools/
│   │   ├── registry.py              # specs, invoke, device proxy
│   │   ├── builtin.py               # server-side tools (time, timers)
│   │   └── policy.py                # allowlist, schema validation, rate limits
│   ├── admin/
│   │   └── http_api.py              # /healthz, /metrics, /ota/manifest
│   └── diagnostics/                 # port of ANIMA diagnostics (section 6.13)
└── tests/                           # section 9
```

Dependencies (verify versions): `websockets`, `numpy`, `scipy` (resampling), `faster-whisper`, `kokoro-onnx`, `silero-vad` (or its ONNX runtime path, to avoid a PyTorch install), `openai` (OpenAI-compatible client), `opuslib` or another libopus binding (requires the system libopus), `pydantic`, `jsonschema`, `pyyaml`, `aiohttp` (admin API), `pytest`, `pytest-asyncio`.

### 6.2 config.py

```python
@dataclass(frozen=True)
class Config:
    # network
    host: str = '0.0.0.0'; port: int = 8765
    device_tokens: dict = field(default_factory=dict)    # device_id -> token, from env or file
    max_sessions: int = 2
    # audio
    up_rate: int = 16000; down_rate: int = 24000; frame_ms: int = 20
    pacer_lead_ms: int = 1000
    # endpointing
    vad_onset: float = 0.65; vad_continue: float = 0.45
    min_speech_ms: int = 128
    fixed_silence_ms: int = 700          # FixedPolicy; semantic policy comes in phase 6
    silence_max_ms: int = 1100
    listen_timeout_ms: int = 6000        # no speech after listen.start
    max_turn_ms: int = 20000
    min_audio_ms: int = 500; min_audio_rms: float = 0.01
    # stt
    whisper_model: str = 'base.en'; whisper_compute: str = 'int8'; whisper_device: str = 'cpu'
    # llm
    llm_provider: str = 'groq'           # 'groq' | 'ollama' | 'openai'
    llm_model: str = ''                  # required; validated at startup
    llm_base_url: str = ''
    llm_max_tokens: int = 150; llm_temperature: float = 0.4
    history_turns: int = 10; max_tool_rounds: int = 3
    llm_connect_retries: int = 3
    # tts
    kokoro_model: str; kokoro_voices: str; voice: str = 'af_bella'; speed: float = 1.05
    first_phrase_min_chars: int = 8; min_phrase_chars: int = 15; max_phrase_chars: int = 200
    # tools
    tool_timeout_ms: int = 2000
    fast_path_intents: bool = True

def validate(c):
    assert c.frame_ms in (10, 20, 40, 60)
    assert c.fixed_silence_ms <= c.silence_max_ms
    assert c.pacer_lead_ms >= 2 * c.frame_ms
    assert c.vad_continue < c.vad_onset              # hysteresis
    assert c.llm_model, 'LLM_MODEL must be set'
    assert c.llm_max_tokens <= 300                   # spoken answers stay short
```

### 6.3 Transport: ws\_server.py and Session

```python
async def handler(ws):
    dev = authenticate(ws.request.headers, cfg)           # close 4401 on failure
    hello = await wait_json(ws, 'hello', timeout=5)       # else close
    if hello.proto != PROTO_VERSION:
        await send_error(ws, 'E_PROTO_VERSION', fatal=True); return
    if len(registry) >= cfg.max_sessions:
        await send_error(ws, 'E_BUSY', fatal=True); return
    session = Session(dev, ws, cfg, models, provider, hello)
    registry.add(session)
    await session.send(HelloAck(proto=1, session_id=session.id, server=VERSION,
                                listen_timeout_ms=cfg.listen_timeout_ms,
                                max_turn_ms=cfg.max_turn_ms, ota=ota_offer_for(dev, hello.fw)))
    try:
        await session.run()
    finally:
        session.close(); registry.remove(session)

class Session:
    async def run(self):
        stages = [ingest_stage, stt_stage, llm_stage, tts_stage, egress_stage]
        stage_tasks = [supervise(name_of(s), lambda s=s: s(self)) for s in stages]
        await asyncio.gather(self.reader(), *stage_tasks)  # reader ending cancels the rest

    async def reader(self):
        async for msg in self.ws:
            if isinstance(msg, bytes):
                self.on_audio(msg)
            else:
                self.on_json(parse_message(msg))

    def on_audio(self, raw):
        f = decode_frame(raw)                             # validates kind, length >= 12, flags
        if f is None:
            return self.metrics.bad_frames += 1
        if f.kind != KIND_UP or f.turn != self.current_turn or self.state != LISTENING:
            return self.metrics.dropped_frames += 1
        put_drop_oldest(self.ingest_q, (f.turn, f))       # bounded; warn when it drops

    def on_json(self, m):
        if m.type == 'listen.start': self.begin_turn(m.turn, m.reason)
        elif m.type == 'listen.end': self.endpointer_force_end(m.turn)
        elif m.type == 'abort' and m.turn == self.current_turn: self.cancel_turn('aborted')
        elif m.type == 'tool.result': self.tools.resolve(m.id, m)
        elif m.type == 'playback': self.metrics.on_playback(m)
        elif m.type == 'telemetry': self.telemetry = m
```

Server-side session state: `IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`. It mirrors the device and is used to drop late audio. Queues per session: `ingest_q`, `stt_q`, `llm_q`, `token_q`, `phrase_q` (maxsize 4), `egress_q`, all bounded.

### 6.4 Audio: Opus, re-chunking, endpointing

`opus_codec.py`:

- `OpusDecoder(rate=16000, channels=1)`. `decode(packet) -> float32 array` (320 samples per 20 ms frame). When `seq` shows a gap of 1 to 3 frames, call the decoder with no data to get concealment audio for each missing frame. Larger gaps reset the endpointer buffer and log a warning.
- `OpusEncoder(rate=24000, channels=1, application='voip', bitrate=28000)`. `encode_frame(int16[480]) -> bytes`. It keeps a residual buffer so any chunk of TTS PCM can be pushed in and exact 480-sample frames come out. `flush()` pads the last partial frame with zeros.
- If Kokoro returns a rate other than 24 kHz, resample first with `scipy.signal.resample_poly`.

`rechunk.py`: `Rechunker(size)` collects samples and yields fixed-size blocks. Silero VAD needs 512-sample blocks (32 ms at 16 kHz) but Opus frames are 320 samples, so the endpointer re-chunks.

`endpointer.py`:

```python
class EndOfTurnPolicy(Protocol):
    def decide(self, silence_ms, speech_ms, partial_text) -> 'END' | 'WAIT': ...

class FixedPolicy:                    # v1
    def decide(self, silence_ms, speech_ms, partial_text):
        return 'END' if silence_ms >= cfg.fixed_silence_ms else 'WAIT'
# phase 6: SemanticPolicy asks a small classifier whether the partial transcript is
# a finished thought; ends early at ~400 ms of silence if yes, waits up to silence_max_ms if no.

class Endpointer:
    BLOCK_MS = 32
    def __init__(self, cfg, vad, policy):
        self.state = WAITING; self.blocks = []; self.total_ms = 0
        self.speech_ms = 0; self.silence_ms = 0; self.rechunk = Rechunker(512)

    def feed(self, pcm):
        for block in self.rechunk.push(pcm):
            p = vad.prob(block)
            thr = cfg.vad_continue if self.state == IN_SPEECH else cfg.vad_onset
            speech = p > thr
            self.blocks.append(block); self.total_ms += self.BLOCK_MS
            if self.state == WAITING:
                self.speech_ms = self.speech_ms + self.BLOCK_MS if speech else 0
                if self.speech_ms >= cfg.min_speech_ms:
                    self.state = IN_SPEECH; self.silence_ms = 0
                elif self.total_ms >= cfg.listen_timeout_ms:
                    return Result('no_speech')
            else:
                self.silence_ms = 0 if speech else self.silence_ms + self.BLOCK_MS
                if policy.decide(self.silence_ms, self.speech_ms, None) == 'END':
                    return Result('endpoint', audio=concat(self.blocks))
                if self.total_ms >= cfg.max_turn_ms:
                    return Result('max_len', audio=concat(self.blocks))
        return None

    def force_end(self):              # push-to-talk release
        return Result('endpoint', audio=concat(self.blocks))
```

The device sends audio that starts after the wake word, so the wake word itself is not transcribed. Port `dsp.py` unchanged from ANIMA: `trim_trailing_silence` (keep about 320 ms after the last voiced chunk), `normalize` (peak 0.95), and the hallucination filter for short Whisper outputs such as thank you.

### 6.5 Stages: ingest and stt

```python
async def ingest_stage(s):
    while True:
        turn, frame = await s.ingest_q.get()
        if s.is_stale(turn): continue
        pcm = s.decoder.decode(frame.payload, seq=frame.seq)
        res = s.endpointer.feed(pcm)
        if res is None: continue
        s.state = PROCESSING
        s.latency.endpoint_at = now()
        await s.send(ListenStop(turn=turn, reason=res.reason))
        if res.reason == 'no_speech':
            s.state = IDLE; continue
        await s.stt_q.put((turn, res.audio))

async def stt_stage(s):
    while True:
        turn, audio = await s.stt_q.get()
        if s.is_stale(turn): continue
        audio = dsp.trim_trailing_silence(audio); dur = len(audio) / s.cfg.up_rate
        if dur * 1000 < s.cfg.min_audio_ms or dsp.rms(audio) < s.cfg.min_audio_rms:
            s.finish_turn(turn, 'empty'); continue
        text = await s.models.run_cpu(s.models.whisper.transcribe, dsp.normalize(audio))
        if s.is_stale(turn): continue
        text = text.strip()
        s.latency.stt_done_at = now()
        if not text or dsp.is_hallucination(text, dur):
            s.finish_turn(turn, 'empty'); continue
        await s.send(Stt(turn=turn, text=text))
        await s.llm_q.put((turn, text))
```

`finish_turn(turn, why)` sends `tts.stop(reason=done)` only if speech had started, sets state IDLE, and logs. `ModelHub.run_cpu` runs a function in a thread pool guarded by one semaphore per model so two sessions cannot thrash the CPU.

### 6.6 LLM provider interface and the llm stage

```python
# providers/base.py
@dataclass
class TextDelta: text: str
@dataclass
class ToolCall:  id: str; name: str; args: dict
@dataclass
class Done:      reason: str

class LLMProvider(Protocol):
    async def validate(self) -> None: ...
    def stream(self, messages, tools, scope: TurnScope) -> AsyncIterator[TextDelta | ToolCall | Done]: ...

# providers/openai_compat.py
class OpenAICompat:
    def __init__(self, base_url, api_key): self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    async def validate(self):
        ids = [m.id async for m in self.client.models.list()]
        if cfg.llm_model not in ids:
            raise StartupError('Model ' + cfg.llm_model + ' not offered. Available: ' + ', '.join(ids))
    async def stream(self, messages, tools, scope):
        resp = await self.client.chat.completions.create(model=cfg.llm_model, messages=messages,
                   tools=tools or None, stream=True, max_tokens=cfg.llm_max_tokens,
                   temperature=cfg.llm_temperature)
        try:
            async for chunk in resp:
                if scope.cancelled.is_set(): break
                # yield TextDelta for content; assemble ToolCall from tool_call deltas; yield Done at the end
        finally:
            await resp.close()               # always release the connection
```

`validate()` runs once at startup and fails fast with the list of available models. This guards against a wrong model name silently breaking every turn.

```python
async def llm_stage(s):
    while True:
        turn, text = await s.llm_q.get()
        if s.is_stale(turn): continue
        if s.cfg.fast_path_intents and (hit := intents.match(text, s)):
            await intents.run(hit, s, turn); continue
        s.history.append(user(text))
        ok = True
        for _round in range(s.cfg.max_tool_rounds):
            msgs = [system_prompt(s)] + s.history[-s.cfg.history_turns * 2:]
            calls, spoken = [], []
            try:
                stream = await retry_with_backoff(s.provider.stream_open, msgs, s.tools.specs(), s.scope,
                                                  max_retries=s.cfg.llm_connect_retries, stage='llm')
                async for ev in stream:
                    if s.is_stale(turn): break
                    if isinstance(ev, TextDelta):
                        if not spoken: s.latency.llm_first_token_at = now()
                        spoken.append(ev.text); await s.token_q.put((turn, ev.text))
                    elif isinstance(ev, ToolCall):
                        calls.append(ev)
            except Exception:
                s.history.pop(); await s.token_q.put((turn, FALLBACK_APOLOGY)); ok = False; break
            if s.is_stale(turn): break
            if not calls:
                s.history.append(assistant(''.join(spoken))); break
            s.history.append(assistant_tool_calls(spoken, calls))
            for c in calls:
                result = await s.tools.invoke(turn, c)           # policy, timeout, device proxy
                s.history.append(tool_result(c.id, result))
        if not s.is_stale(turn):
            await s.token_q.put((turn, END_OF_RESPONSE))
        s.history = trim_history(s.history, s.cfg.history_turns)   # keep tool messages with their turn
```

Retry applies only before the first token. A stream that fails midway ends the reply, because speech has probably started already. Confirm that the chosen model supports tool calling before relying on tools.

### 6.7 TTS stage

Port ANIMA's accumulator and synthesizer with three changes: output goes to `egress_q` as PCM plus the sentence text, the first phrase is released early, and the Kokoro call is wrapped in `run_cpu`.

```python
async def accumulator(s):
    buf, first = '', True
    while True:
        turn, tok = await s.token_q.get()
        if s.is_stale(turn): buf, first = '', True; continue
        if tok is END_OF_RESPONSE:
            if buf.strip(): await s.phrase_q.put((turn, buf))
            await s.phrase_q.put((turn, END_OF_RESPONSE)); buf, first = '', True; continue
        buf += tok
        min_chars = s.cfg.first_phrase_min_chars if first else s.cfg.min_phrase_chars
        if (len(buf) >= min_chars and buf.rstrip()[-1:] in '.!?,:;') or len(buf) >= s.cfg.max_phrase_chars:
            await s.phrase_q.put((turn, buf)); buf, first = '', False

async def synthesizer(s):
    while True:
        turn, phrase = await s.phrase_q.get()
        if s.is_stale(turn): continue
        if phrase is END_OF_RESPONSE:
            await s.egress_q.put((turn, END_OF_SPEECH)); continue
        try:
            pcm, sr = await s.models.run_cpu(s.models.kokoro.create, strip_markdown(phrase),
                                             voice=s.cfg.voice, speed=s.cfg.speed)
        except Exception:
            pcm, sr = generate_error_tone(24000), 24000
        if s.is_stale(turn): continue
        s.latency.mark_once('tts_first_phrase_at')
        await s.egress_q.put((turn, Chunk(pcm, sr, text=phrase)))
```

If the installed `kokoro-onnx` offers a streaming API, use it to start audio sooner within a phrase. The macOS `say` fallback from ANIMA is optional and only for Mac hosts.

### 6.8 Egress and the pacer

```python
class Pacer:
    def __init__(self, lead_ms, frame_ms):
        self.lead = lead_ms / 1000; self.frame = frame_ms / 1000; self.t0 = None; self.sent = 0
    async def wait(self):
        loop = asyncio.get_running_loop(); now_t = loop.time()
        if self.t0 is None: self.t0 = now_t
        due = self.t0 + self.sent * self.frame - self.lead
        if due < now_t - 0.2:                  # starved: the device buffer is empty, restart the clock
            self.t0 = now_t; self.sent = 0; due = now_t - self.lead
        if due > now_t: await asyncio.sleep(due - now_t)
        self.sent += 1

async def egress_stage(s):
    pacer, started, seq = None, False, 0
    while True:
        turn, item = await s.egress_q.get()
        if s.is_stale(turn): pacer, started = None, False; continue
        if item is END_OF_SPEECH:
            for fr in s.encoder.flush(): await send_frame(s, turn, fr, seq, last=True); seq += 1
            await s.send(TtsStop(turn=turn, reason='done')); s.state = IDLE
            pacer, started = None, False; continue
        if not started:
            await s.send(TtsStart(turn=turn)); s.state = SPEAKING; started = True
            pacer = Pacer(s.cfg.pacer_lead_ms, s.cfg.frame_ms); s.encoder.reset()
            s.latency.first_frame_at = now()
        await s.send(Reply(turn=turn, text=item.text))
        for fr in s.encoder.push(to_int16(resample_if_needed(item.pcm, item.sr))):
            if s.is_stale(turn): break
            await pacer.wait()
            await send_frame(s, turn, fr, seq, first=(seq == 0)); seq += 1
    # send_frame builds the 12-byte header from section 4.2
```

The `LAST` flag is set when known, but the device must treat `tts.stop` as the real end marker.

### 6.9 Fast-path intents (skip the LLM)

`intents.py` matches a small set of commands with regular expressions after lowercasing and stripping punctuation. A hit calls a device tool directly through the tool registry and speaks a canned reply through the normal TTS path, so there is no LLM round trip. A flag turns the feature off.

| Pattern (examples) | Action | Reply |
| --- | --- | --- |
| stop, be quiet, cancel | `cancel_turn` | none |
| volume up / down | `device.set_volume` relative step 10 | Volume up. |
| set volume to N (0 to 100) | `device.set_volume` N | Volume N. |
| turn on / off the lamp or light | `device.lamp_set` | Done. |
| what time is it | server tool `time.now` | spoken time |

### 6.10 Tools: registry, policy, device proxy

```yaml
# tools.yaml
device:
  set_volume:     {risk: safe, rate_per_min: 30}
  set_brightness: {risk: safe, rate_per_min: 30}
  lamp_set:       {risk: safe, rate_per_min: 20}
  get_status:     {risk: safe, rate_per_min: 30}
server:
  time.now:       {risk: safe}
forbidden_always: [reboot, upgrade_firmware, wifi_*, factory_reset, set_token]
```

```python
class ToolRegistry:
    def specs(self):                          # OpenAI tool schema for the LLM
        return [to_schema(t) for t in self.server_tools + self.device_tools_from_hello()
                if policy.exposed(t)]

    async def invoke(self, turn, call):
        spec = self.lookup(call.name)
        verdict = policy.check(spec, call.args, self.session)   # allowlist, jsonschema, rate limit
        if not verdict.ok:
            return json.dumps({'error': 'E_TOOL_DENIED', 'why': verdict.reason})
        if spec.where == 'server':
            return truncate(await asyncio.wait_for(spec.fn(**call.args), 2.0), 500)
        fut = self.pending[call.id] = asyncio.get_running_loop().create_future()
        await self.session.send(ToolCall(turn=turn, id=call.id, name=spec.device_name, args=call.args,
                                         timeout_ms=self.cfg.tool_timeout_ms))
        try:
            res = await asyncio.wait_for(fut, self.cfg.tool_timeout_ms / 1000)
            return truncate(json.dumps(res), 500)
        except asyncio.TimeoutError:
            return json.dumps({'error': 'E_TOOL_TIMEOUT'})
        finally:
            self.pending.pop(call.id, None)
```

In v1 only `risk: safe` tools are exposed to the LLM. The `confirm` class is reserved for later. The `forbidden_always` list is enforced in code, so editing `tools.yaml` cannot expose those tools.

### 6.11 main.py, supervisor and admin API

```python
async def main():
    cfg = load_config(); validate(cfg); setup_logging()
    models = await ModelHub.load(cfg)        # Whisper, Kokoro, Silero; each warmed up once
    provider = make_provider(cfg); await provider.validate()
    admin = start_admin_api(cfg, registry)
    async with websockets.serve(handler, cfg.host, cfg.port, max_size=65536,
                                ping_interval=10, ping_timeout=30):
        await asyncio.Future()               # run until cancelled

async def supervise(name, factory, session):
    backoff, crashes = 0.5, deque(maxlen=5)
    while True:
        try:
            await factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception('stage %s crashed', name)
            crashes.append(now())
            if len(crashes) == 5 and crashes[-1] - crashes[0] < 60:
                await session.send(Error(code='E_INTERNAL', fatal=True)); await session.close(); return
            await session.send(Alert(level='warn', code='stage_restart', text=name))
            await asyncio.sleep(backoff); backoff = min(backoff * 2, 10)
```

The admin API listens on a separate port and requires its own bearer token. Endpoints: `GET /healthz`, `GET /metrics` (JSON counters and recent latencies), `GET /ota/manifest?device_id=` (version, URL, SHA-256, size). It is the only place that can offer firmware.

### 6.12 Metrics

`TurnLatency` records `listen_start`, `endpoint_at`, `stt_done_at`, `llm_first_token_at`, `tts_first_phrase_at` and `first_frame_at`. When the first frame is sent, log one line: `[latency] session=<id> turn=<n> endpoint=<s> stt=<s> llm_ttft=<s> tts=<s> ttfa=<s>`, where `ttfa` is `first_frame_at - endpoint_at`. Counters: stale drops per stage, bad frames, dropped frames, underruns reported by the device, tool calls and failures, reconnects.

### 6.13 Diagnostics

Port ANIMA's `anima_check.py` and collectors for hardware, STT, LLM, TTS and network. Replace the microphone and echo collectors, since the server has no microphone, with a `ws_loopback` collector. It plays a recorded WAV through `tools/fake_device.py` and measures `ttfa`, frame pacing accuracy and dropped frames. Keep the health gates and add `ttfa_p50_s` (warn at 1.5, fail at 2.5). Keep the report generators and the run-diff feature.

## 7. Firmware design (ESP32-S3, ESP-IDF 5.x, C++)

### 7.1 Directory layout

```
firmware/
├── CMakeLists.txt
├── sdkconfig.defaults
├── sdkconfig.defaults.esp32s3
├── partitions.csv
├── main/
│   ├── CMakeLists.txt
│   ├── idf_component.yml            # esp-sr, esp_audio_codec, esp_websocket_client, cJSON, ...
│   ├── main.cc                      # app_main: init order, then App::run()
│   ├── config.h                     # all firmware constants (one place)
│   ├── app/
│   │   ├── app.h / app.cc           # event loop, owns state and turn counter
│   │   ├── state_machine.h / .cc    # table-driven transitions (section 7.5)
│   │   └── events.h                 # Event struct and EventType enum
│   ├── audio/
│   │   ├── audio_io.h / .cc         # I2S init, read, write, mute, flush (INMP441 + MAX98357A)
│   │   ├── ring_buffer.h            # lock-free SPSC ring buffer (PSRAM backed)
│   │   ├── jitter_buffer.h / .cc    # playback buffer with prebuffer and underrun counting
│   │   ├── opus_enc.cc / opus_dec.cc
│   │   ├── wake_word.h / .cc        # ESP-SR front end + WakeNet wrapper
│   │   └── cues.h / .cc             # short PCM cues (wake chime, error, ready)
│   ├── net/
│   │   ├── wifi_manager.cc          # station connect, backoff, power-save policy
│   │   ├── provisioning.cc          # first-run Wi-Fi and server setup
│   │   ├── ws_client.h / .cc        # WebSocket client, reconnect, send queue
│   │   ├── protocol.h / .cc         # frame header, JSON build and parse
│   │   ├── protocol_gen.h           # generated from /protocol (do not edit)
│   │   └── discovery.cc             # mDNS lookup of anima.local
│   ├── tools/
│   │   ├── tool_registry.h / .cc    # table of allowed tools, validation, dispatch
│   │   └── tools_builtin.cc         # set_volume, set_brightness, lamp_set, get_status
│   ├── ui/
│   │   ├── ui.h                     # interface: show_state, show_text, show_emotion
│   │   ├── led_ui.cc                # status LED patterns (phase 2)
│   │   └── lcd_ui.cc                # LCD UI (phase 6)
│   ├── sys/
│   │   ├── settings.h / .cc         # NVS wrapper (typed get/set)
│   │   ├── ota.h / .cc              # download, verify, switch slot, mark valid
│   │   ├── buttons.cc               # debounced tap, long press, press and release
│   │   └── diag.cc                  # heap, task stats, self-test mode
│   └── boards/
│       ├── board.h                  # pins and capabilities interface
│       └── breadboard_s3/           # pins.h, board.cc (section 8)
└── host_test/                       # protocol, ring buffer, state machine tests on the PC
```

### 7.2 Build configuration essentials

Set these in `sdkconfig.defaults*` and confirm each option name in the installed ESP-IDF version:

- Target esp32s3, 16 MB flash, octal PSRAM 8 MB at 80 MHz, CPU 240 MHz.
- PSRAM available to `malloc` for large buffers. Keep DMA buffers, I2S buffers and audio task stacks in internal RAM.
- App rollback enabled (bootloader checks that a new image marks itself valid).
- Task watchdog on, with the audio tasks subscribed.
- mbedTLS allocations in PSRAM, so TLS does not take internal RAM.
- Wi-Fi power save off while a conversation is active, modem power save allowed in IDLE. Measure the wake-up cost before choosing.
- Log level INFO in release builds, with no logging inside audio loops.

### 7.3 Partition table (16 MB, adjust after the first build)

```
# Name,    Type, SubType, Offset,   Size
nvs,       data, nvs,     0x9000,   0x6000
otadata,   data, ota,     0xf000,   0x2000
phy_init,  data, phy,     0x11000,  0x1000
ota_0,     app,  ota_0,   0x20000,  0x300000
ota_1,     app,  ota_1,   0x320000, 0x300000
model,     data, spiffs,  0x620000, 0x400000    # ESP-SR models
storage,   data, spiffs,  0xa20000, 0x200000    # cues, optional assets
```

The app image must stay under 3 MB. About 4 MB of flash stays free for growth. Confirm the partition name and type the ESP-SR model loader expects.

### 7.4 FreeRTOS tasks (starting values, tune with measurements)

| Task | Core | Priority | Stack | Role |
| --- | --- | --- | --- | --- |
| audio\_in | 1 | 9 | 4 KB internal | I2S read 20 ms blocks, push to mic ring, feed wake word |
| afe\_wake | 1 | 8 | 8 KB internal | ESP-SR front end and WakeNet, posts WAKE |
| audio\_out | 1 | 9 | 4 KB internal | jitter buffer to I2S write, writes silence on underrun |
| opus\_enc | 0 | 5 | 24 KB (PSRAM stack ok) | encodes mic frames while uplink is active |
| opus\_dec | 0 | 6 | 24 KB (PSRAM stack ok) | decodes downlink packets into the jitter buffer |
| ws\_client | 0 | 5 | 6 KB | esp\_websocket\_client task, posts events only |
| app | 0 | 4 | 8 KB | event loop and state machine |
| ui | 0 | 2 | 6 KB | LED and LCD updates |
| ota | 0 | 3 | 8 KB | created on demand, deleted when done |

Wi-Fi and LwIP run on core 0 by default, so DSP and I2S live on core 1. Check this against sdkconfig, then use `vTaskGetRunTimeStats` and stack high-water marks to rebalance. Rules: no heap allocation, logging or blocking mutexes inside `audio_in` and `audio_out` loops; communicate through ring buffers and the event queue; the ws event handler never blocks and never parses large payloads inline.

Buffers: mic ring 2 s of 16 kHz int16 (64 KB, PSRAM); jitter buffer 1.5 s of 24 kHz int16 (72 KB, PSRAM); decode packet queue 100 packets (about 2 s); uplink send queue 10 frames (200 ms, drop oldest and count).

### 7.5 State machine

States: `BOOT`, `PROVISIONING`, `CONNECTING_WIFI`, `CONNECTING_SERVER`, `IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `UPDATING`, `FATAL`.

| From | Event | To | Actions |
| --- | --- | --- | --- |
| BOOT | boot done, credentials stored | CONNECTING\_WIFI | start station |
| BOOT | no credentials, or BOOT button held | PROVISIONING | start provisioning |
| PROVISIONING | credentials saved | CONNECTING\_WIFI | stop provisioning |
| CONNECTING\_WIFI | wifi up | CONNECTING\_SERVER | resolve host, open WebSocket |
| CONNECTING\_WIFI | 5 minutes without link | PROVISIONING | show error |
| CONNECTING\_SERVER | hello\_ack | IDLE | arm wake word, mark OTA image valid if self-test passed |
| any connected state | ws down or wifi down | CONNECTING\_SERVER or CONNECTING\_WIFI | flush audio, backoff |
| IDLE | WAKE or PTT down | LISTENING | turn++, cue, send listen.start, start uplink |
| LISTENING | listen.stop (current turn) | THINKING | stop uplink |
| LISTENING | PTT up | LISTENING | send listen.end |
| LISTENING | 25 s without listen.stop | IDLE | send abort, stop uplink |
| THINKING | tts.start (current turn) | SPEAKING | mute mic, start prebuffer |
| THINKING | tts.stop with no audio | IDLE | none |
| SPEAKING | tts.stop and buffer drained | IDLE | wait 300 ms tail, unmute mic, send playback finished |
| SPEAKING or THINKING | tap (barge-in) | LISTENING | flush playback, turn++, send listen.start(barge\_in), unmute mic |
| IDLE | OTA offer accepted | UPDATING | start ota task |
| UPDATING | success | reboot | none |
| UPDATING | failure | IDLE | alert on display |

Implement the table as a data structure (`{from, event, to, action_fn}`), looked up in the event loop. An event with no matching row is logged and ignored. Messages with a stale turn never reach the state machine; they are dropped in `ws_client` (rule T7).

### 7.6 Core pseudocode

```cpp
extern 'C' void app_main() {
    nvs_init(); Settings::load();
    auto board = Board::create();            // pins, capabilities
    board->init_gpio(); Ui::init(board);
    Audio::init(board);                      // I2S RX 16 kHz, I2S TX 24 kHz, rings, tasks (idle)
    WakeWord::init();                        // load model from the model partition
    Net::init();
    App::instance().run();                   // never returns
}

void App::run() {
    for (;;) {
        Event e; xQueueReceive(events, &e, portMAX_DELAY);
        if (e.has_turn && e.turn < turn_) { stats.stale++; continue; }       // rule T7
        const Transition* t = table.find(state_, e.type);
        if (!t) { log_unhandled(state_, e); continue; }
        t->action(*this, e);
        state_ = t->to; Ui::show_state(state_);
    }
}
```

Audio input and wake word:

```cpp
void audio_in_task(void*) {
    int16_t block[320];                              // 20 ms at 16 kHz
    for (;;) {
        i2s_read_mono16(block, 320);                 // converts the 32-bit INMP441 slots; verify the shift
        if (mic_muted) continue;                     // half-duplex: keep draining the DMA, discard
        mic_ring.push(block, 320);
        if (wake_armed) wake_word.feed(block, 320);  // ESP-SR chunk size handled inside
    }
}

void afe_wake_task(void*) {
    for (;;) {
        if (wake_word.fetch_detected()) App::post(Event{WAKE});
        else vTaskDelay(1);
    }
}

void App::on_wake_or_ptt(Reason r) {                 // IDLE to LISTENING
    turn_++;
    Cues::play(WAKE_CUE);                            // played before the mic opens
    mic_ring.discard_older_than(PREROLL_MS);         // optional short pre-roll
    ws.send_json(listen_start(turn_, r));
    uplink_active = true; mic_muted = false; wake_armed = false;
}
```

Uplink (Opus encode and send):

```cpp
void opus_enc_task(void*) {
    int16_t pcm[320]; uint8_t pkt[256]; uint16_t seq = 0; bool first = true;
    for (;;) {
        if (!uplink_active) { seq = 0; first = true; vTaskDelay(pdMS_TO_TICKS(5)); continue; }
        if (!mic_ring.pop(pcm, 320, 20 /*ms wait*/)) continue;
        int n = opus_encode_frame(pcm, pkt);
        ws.send_audio(KIND_UP, first ? FLAG_FIRST : 0, seq++, turn_, t_ms(), pkt, n);   // drop oldest if queue full
        first = false;
    }
}
```

Downlink (receive, decode, play):

```cpp
void ws_on_binary(const uint8_t* d, size_t n) {          // runs in the ws task: validate and enqueue only
    Frame f; if (!parse_frame(d, n, &f) || f.kind != KIND_DOWN) return;
    if (f.turn != turn_) { stats.stale_audio++; return; }   // rule T7
    dec_queue.try_push(copy_packet(f));                    // bounded; counts drops
}

void opus_dec_task(void*) {
    int16_t pcm[480];                                      // 20 ms at 24 kHz
    for (;;) {
        Packet p; if (!dec_queue.pop(&p, 50)) continue;
        if (p.turn != turn_) { free_packet(p); continue; }
        int n = opus_decode_frame(p.data, p.len, pcm);
        jitter.push(pcm, n);
        if (!playing && jitter.buffered_ms() >= PREBUFFER_MS) { playing = true; ws.send_json(playback(turn_, 'started')); }
    }
}

void audio_out_task(void*) {
    int16_t out[480];
    for (;;) {
        if (!playing) { vTaskDelay(pdMS_TO_TICKS(5)); continue; }
        if (jitter.pop(out, 480)) i2s_write_mono(out, 480);
        else { i2s_write_silence(480); stats.underruns++; note_underrun_rate_limited(); }
        if (tts_stopped_flag && jitter.empty()) App::post(Event{PLAYBACK_DONE});
    }
}
```

Barge-in and flush:

```cpp
void App::on_tap_during_speech() {
    playing = false; i2s_zero_dma_buffer(); jitter.clear(); dec_queue.clear();
    ws.send_json(playback(turn_, 'flushed'));
    turn_++; mic_muted = false; uplink_active = true;
    ws.send_json(listen_start(turn_, BARGE_IN));
}
```

Playback finish, with the tail that replaces ANIMA's post-speech mute:

```cpp
void App::on_playback_done() {
    vTaskDelay(pdMS_TO_TICKS(MIC_TAIL_MS));          // 300 ms of room decay
    mic_muted = false; wake_armed = true; tts_stopped_flag = false;
    ws.send_json(playback(turn_, 'finished'));
}
```

### 7.7 WebSocket client and reconnect

- Use the ESP-IDF websocket client component. Headers: `Authorization: Bearer <token>`, `X-Device-Id`. Ping every 10 s, network timeout 10 s. Disable its built-in auto-reconnect and use the app-level backoff below, so state stays consistent.
- On connect: send `hello` with firmware version, board name, features, audio settings, the tool list and `last_turn`.
- Receive path: accumulate text fragments until the message is complete, parse with cJSON, post an event. Binary messages go through `ws_on_binary` above.
- Backoff: 1, 2, 4, 8, 16, 30 s, plus up to 20 percent random jitter. Reset after a successful `hello_ack`.
- On disconnect during LISTENING, THINKING or SPEAKING: stop uplink, flush playback, unmute, go to CONNECTING\_SERVER.

### 7.8 Tools on the device

```cpp
struct Tool {
    const char* name; const char* desc; const char* params_schema;   // JSON Schema text
    Risk risk; ToolResult (*fn)(const cJSON* args);
};
static const Tool kTools[] = {
    {'set_volume',     'Set speaker volume 0-100',     SCHEMA_LEVEL, SAFE, tool_set_volume},
    {'set_brightness', 'Set screen brightness 0-100',  SCHEMA_LEVEL, SAFE, tool_set_brightness},
    {'lamp_set',       'Turn the lamp relay on or off', SCHEMA_ONOFF, SAFE, tool_lamp_set},
    {'get_status',     'Battery, volume, wifi signal',  SCHEMA_NONE,  SAFE, tool_get_status},
};

void App::on_tool_call(const ToolCall& c) {
    if (c.turn != turn_)                  return reply_err(c, 'stale');
    const Tool* t = find_tool(c.name);
    if (!t || t->risk != SAFE)            return reply_err(c, 'denied');
    if (!validate_args(t->params_schema, c.args)) return reply_err(c, 'bad_args');
    ToolResult r = t->fn(c.args);         // must finish in under 100 ms
    ws.send_json(tool_result(c.turn, c.id, r.ok, r.payload));
}
```

There is no tool for reboot, firmware, Wi-Fi settings or the token. The relay output is low at boot, and the lamp tool clamps repeated toggling (maximum 10 changes per minute). If the relay ever switches mains voltage, use a certified isolated relay module and enclosure; software cannot make that safe.

### 7.9 Provisioning, settings, OTA

- **Settings (NVS):** `server_host`, `server_port`, `device_token`, `volume`, `brightness`, `wake_enabled`. Device ID is derived from the MAC. Never log the token.
- **Provisioning:** use ESP-IDF's official Wi-Fi provisioning component with its authenticated security mode, plus one custom endpoint that receives server host, port and token. A plain open hotspot with an HTML form sends the Wi-Fi password in the clear, so avoid it. Entry: first boot without credentials, or hold BOOT at power-up.
- **OTA:** when `hello_ack` carries an offer, and the state is IDLE, download with `esp_https_ota` into the inactive slot, compare SHA-256 with the manifest, set the boot partition, reboot. On the next boot, mark the image valid after a local self-test (audio init OK and Wi-Fi up). Do not wait for the server, so a server outage cannot trigger a pointless rollback. Optional later: signed images.

### 7.10 Wake word and front end

- Use ESP-SR WakeNet with a stock wake word first. Custom words need Espressif's training path or a MultiNet-based phrase, and are less accurate. Alternative to evaluate: microWakeWord, which allows open custom training.
- Front end in v1: noise suppression and automatic gain only, if CPU allows. No AEC (we are half-duplex).
- Push-to-talk always works, even if the wake word model fails to load.
- The model lives in the `model` partition. Log the free heap after loading.

### 7.11 UI

`Ui` interface: `show_state(state)`, `show_text(str)`, `show_emotion(str)`, `notify(str)`. Phase 2 ships `LedUi`: IDLE off, LISTENING solid, THINKING slow blink, SPEAKING fast pulse, errors three quick blinks, PROVISIONING double blink. Phase 6 adds `LcdUi` for the 128x160 panel (status bar, emotion glyph, scrolling subtitle from `stt` and `reply` messages). The ST7735 may need the ST7789 driver in a compatible mode; verify against the actual panel.

## 8. Hardware defaults

These defaults come from an AI-generated summary of an existing project. **Treat them as unverified.** Confirm against the actual board and wiring, write the result into docs/HARDWARE.md, and only then flash.

| Function | Signal | GPIO (default) |
| --- | --- | --- |
| INMP441 mic | WS | 4 |
|  | SCK | 5 |
|  | SD | 6 |
|  | L/R | tied to GND (left channel) |
| MAX98357A amp | DIN | 7 |
|  | BCLK | 15 |
|  | LRC | 16 |
| ST7735 LCD | MOSI | 11 |
|  | SCLK | 12 |
|  | CS | 10 |
|  | DC | 13 |
|  | RST | 14 |
|  | BL | 21 |
| Buttons | BOOT / tap | 0 |
|  | PTT | 47 |
|  | Volume up / down | 40 / 39 |
| Lamp relay | output | 18 |
| Status LED | output | 48 |

Checks to make:

- On many ESP32-S3 dev boards GPIO 48 drives an addressable RGB LED, not a plain LED. If so, `led_ui.cc` needs the LED strip driver.
- With octal PSRAM, avoid GPIO 26 to 37 and the strapping pins (0, 3, 45, 46) except where a strapping use is intended (GPIO 0 as BOOT).
- I2S: the mic uses one controller at 16 kHz and the amplifier the other at 24 kHz, both mono, Philips format.
- INMP441 sends 24-bit samples in 32-bit slots. Record 3 seconds to a WAV and check level and clipping before tuning the bit shift.

## 9. Testing strategy and the fake device

Goal G6: everything except drivers is testable without hardware. The fake device is the main tool for that.

### 9.1 tools/fake\_device.py

A Python program that behaves like the ESP32 at the protocol level.

```
python tools/fake_device.py --url ws://127.0.0.1:8765/v1/device --token T \
    --wav samples/turn_on_lamp.wav --out out/reply.wav --scenario normal
```

Scenarios: `normal`, `barge_in`, `tool_call`, `no_speech`, `reconnect`, `stale_audio`, `bad_token`.

Behaviour, in order: connect with headers; send `hello` with a tool list; send `listen.start(turn=n)`; stream the WAV as 20 ms Opus frames paced in real time; wait for `listen.stop`; receive `tts.start`, audio and `tts.stop`; write received audio to a WAV; enforce rule T7 (drop stale turns); print a timing summary (`ttfa`, number of frames, gaps). Fault injection flags: `--drop-frames 5`, `--jitter-ms 40`, `--disconnect-at 2.5`, `--late-frames-after-barge-in 10`.

### 9.2 Server tests

Use deterministic fakes for the heavy parts: `FakeWhisper` (returns a scripted transcript), `FakeKokoro` (returns a sine tone of a length proportional to the text), `FakeProvider` (scripted tokens and tool calls, configurable delays and failures). Real models are used only in the Phase 1 acceptance run and in diagnostics.

| Test | What it proves |
| --- | --- |
| test\_protocol\_frames | Header round trip, wrong kind, short frame, bad flags rejected |
| test\_turn\_rules | Higher turn cancels older work; equal or lower turn ignored |
| test\_stale\_all\_stages | Each stage drops stale items before and after its await (port of ANIMA test\_staleness) |
| test\_barge\_in\_race | Late turn N end marker never stops turn N+1 (port of ANIMA test\_barge\_in\_race) |
| test\_endpointer | Synthetic speech and silence: onset, hysteresis, no\_speech timeout, max length, force\_end |
| test\_policy\_fixed | FixedPolicy ends exactly at the configured silence |
| test\_opus\_plc | Gap of 1 to 3 frames conceals; larger gap resets the buffer |
| test\_pacer | Burst equals the lead, then real-time rate; restarts cleanly after starvation |
| test\_llm\_stage | History trim, tool round trip, fallback apology, no retry after first token |
| test\_provider\_validate | Unknown model name fails startup with the list of available models |
| test\_tool\_policy | Forbidden tools never exposed, schema errors rejected, rate limit enforced |
| test\_device\_proxy | Timeout returns E\_TOOL\_TIMEOUT; late result is ignored |
| test\_intents | Fast-path matching table, no LLM call on a hit |
| test\_supervisor | Stage crash restarts it; five crashes in a minute closes the session |
| test\_reconnect | New hello resets session state; old turn work is gone |
| test\_config | Every invariant in `validate()` |

Integration tests start the real server in-process with the fakes above and drive it with the fake device for each scenario. They assert on messages received, order, and timing bounds with generous margins.

### 9.3 Firmware host tests (run on the PC, no board)

Compile these modules for the host with a small CMake project in `host_test/`: protocol framing and JSON building, ring buffer (single producer, single consumer, wraparound), jitter buffer (prebuffer, underrun count), state machine table, tool argument validation. Tests: every row of the section 7.5 table fires once; every unlisted (state, event) pair is ignored without changing state; a stale-turn event never reaches the table.

A shared test vector file (`protocol/vectors.json`) holds example frames and messages. Both the Python and C++ tests read it, so the two sides cannot drift apart.

### 9.4 On-device checks

- **Self-test mode** (a build flag): records 3 s and plays it back, plays a tone, prints microphone RMS, opens the WebSocket and echoes a frame, prints heap and PSRAM, stack high-water marks and run-time stats.
- **Barge-in latency:** log a timestamp when the tap is detected and when I2S output is zeroed. Target 200 ms or less.
- **Soak:** 8 hours with a scripted prompt every few minutes (a second device or a speaker plays the wake word and a question). Heap must stay flat within 5 percent; no task watchdog resets.
- **Fault drills:** switch the router off for 30 s; kill and restart the server mid-reply; block the LLM API; feed the device garbage frames. Each must end in IDLE without a reboot.

## 10. Security and safety

### 10.1 Threats considered

Other devices on the LAN; a prompt-injected or compromised LLM; a stolen device; a malicious firmware image; a compromised server.

### 10.2 Controls

| Area | Control |
| --- | --- |
| Device identity | Random 32-byte token per device, stored in NVS, sent as a bearer token. Server keeps a device\_id to token map. Wrong token closes the socket with 4401. |
| Transport | ws:// on a trusted LAN in v1. The code path for wss:// (certificate pinning or a private CA) must exist before any internet exposure. |
| Tool surface | Allowlist on both sides. Forbidden tools (reboot, firmware, Wi-Fi, token, factory reset) are enforced in code and not configurable. |
| Arguments | Validated against JSON Schema on the server and again on the device. Numeric ranges clamped. |
| Rate limits | Per tool per minute on the server. The lamp also has a device-side limit. |
| Prompt injection | Transcripts, tool results and any fetched web text are data, not instructions. Tool results are truncated to 500 characters. The system prompt states this. |
| OTA | Offered only by the authenticated admin API manifest. Device checks SHA-256. A/B slots with rollback. Optional later: signed images and secure boot. |
| Secrets | Never logged. The admin API uses a separate token and bind address. |
| Privacy | Wake word runs on the device; no audio before wake or button. Server stores no audio by default. Transcripts are logged only at DEBUG level, and the cloud LLM receives text only. Tell the owner that transcripts reach the LLM provider. |
| Visible state | LED shows when audio is being streamed. Optional hardware mute switch cuts the mic supply. |
| Physical safety | Relay output defaults to off. Mains switching only through a certified isolated module. |

## 11. Build phases

Each phase lists deliverables and acceptance tests. Do not move on until the acceptance tests pass and the CHANGELOG is updated.

### Phase 0: Skeleton and protocol package

Deliverables: repository layout from section 3; `protocol/schema.json`, `constants.yaml`, `vectors.json`; `gen.py` producing the Python and C header outputs; docs/PROTOCOL.md from section 4; CI that runs Python tests and the host tests.

Acceptance: generated files import and compile; the frame and message vectors round-trip on both sides.

### Phase 1: Server with fake device

Deliverables: everything in section 6 except intents and semantic endpointing; port of ANIMA core, retry, dsp, diagnostics skeleton; `tools/fake_device.py`; the test suite of section 9.2.

Acceptance: with real Whisper, Kokoro and the chosen LLM, `fake_device --scenario normal` produces a reply WAV and a latency line; `barge_in`, `no_speech`, `reconnect`, `stale_audio` and `tool_call` scenarios pass; LLM outage produces the spoken apology; killing and restarting the server makes the fake device reconnect on its own; `provider.validate()` fails clearly on a wrong model name.

### Phase 2: Firmware audio loop (push-to-talk, LED only)

Deliverables: board pins file; I2S input and output; Opus encode and decode; WebSocket client with backoff; jitter buffer; PTT button; `LedUi`; self-test mode.

Acceptance: hold PTT, speak, release, hear the reply; underruns below 1 percent of frames over 50 turns on the LAN; barge-in tap silences the speaker within 200 ms; heap stays flat over 30 minutes; microphone WAV test shows no clipping.

### Phase 3: Wake word and the full state machine

Deliverables: ESP-SR integration, model partition, table-driven state machine with host tests, mic mute and tail, timeouts, reconnect handling.

Acceptance: 50 consecutive wake-and-ask cycles without a stuck state; false wake count measured over one quiet hour and recorded; router-off and server-kill drills end in IDLE; PTT still works with the wake word disabled.

### Phase 4: Tools, fast path, endpoint tuning

Deliverables: device tool registry, server tool registry and policy, `tools.yaml`, intents module, device proxy; tuning of `fixed_silence_ms` using recorded utterances.

Acceptance: set volume to 30 works with no LLM call; an LLM-driven turn the lamp on works end to end; every forbidden tool is unreachable (tests on both sides); tool timeout and denial are reported to the LLM and spoken sensibly.

### Phase 5: Provisioning, settings, OTA, admin

Deliverables: authenticated provisioning flow including server host and token; NVS settings; OTA with rollback; admin API with manifest; E\_AUTH handling.

Acceptance: a factory-fresh device is provisioned from a phone; an OTA update completes; a deliberately broken image rolls back; wrong token stops retries and shows the error.

### Phase 6: Display, emotion, smarter endpointing

Deliverables: `LcdUi` (status bar, emotion glyph, subtitle); optional emotion tag parsing from the LLM reply; `SemanticPolicy` for end of turn; streaming TTS if the library supports it.

Acceptance: on a set of 30 recorded utterances with natural pauses, fewer cut-offs than FixedPolicy and a lower median `ttfa`, both measured and written in the CHANGELOG.

### Phase 7: Hardening and packaging

Deliverables: 24 hour soak; `anima_check` report in CI; wss support and documentation; optional signed OTA; Docker or systemd packaging for the server; user guide.

Acceptance: soak passes with flat heap and no watchdog resets; diagnostics report is green or has documented warnings.

## 12. Risks, open questions, verification checklist

### 12.1 Risks

| Risk | Mitigation |
| --- | --- |
| Wi-Fi jitter causes audio gaps | Server pacing with 1 s lead, 200 ms prebuffer, jitter buffer, underrun metric |
| Opus encode or decode too slow on the ESP32 | Lower encoder complexity, measure CPU per task, move tasks between cores |
| PSRAM and Wi-Fi contention causes glitches | Keep audio task stacks and DMA buffers in internal RAM; test under load |
| Custom wake word not available in ESP-SR | Stock wake word, push-to-talk, or evaluate microWakeWord |
| Weak server makes Whisper slow | Smaller model, GPU, or faster endpointing to hide latency |
| Chosen LLM lacks tool calling | Fast-path intents cover core commands; verify support before enabling tools |
| Wrong LLM model name | Startup validation lists the available models |
| Half-duplex feels unnatural | Acceptable for v1; later option is hardware echo cancellation with a dedicated audio chip |
| Heavy PyTorch dependency for VAD | Use the ONNX path of the VAD package |
| License conflicts | Original code only; THIRD\_PARTY.md; check licenses of each model and library before release |

### 12.2 Verification checklist (do before writing the related code)

1. ESP-IDF version that works with the chosen esp-sr, esp\_audio\_codec and websocket components.
2. ESP-SR wake word list and the exact model partition format and name.
3. Opus encoder and decoder API and recommended complexity on ESP32-S3.
4. I2S standard-mode API in the installed ESP-IDF (new channel-based driver) for two simplex ports.
5. INMP441 slot format and the correct shift to 16-bit.
6. LED on GPIO 48: plain or addressable.
7. `kokoro-onnx` API: `create`, any streaming variant, expected sample rate.
8. `faster-whisper` model download and warm-up behaviour.
9. Silero VAD package: ONNX usage, block size, state reset call.
10. libopus binding for Python and its install requirements.
11. Whether the selected LLM model supports streaming tool calls.
12. `websockets` library version and the keepalive parameters.

## Appendix A. Constants reference

| Name | Value | Where defined |
| --- | --- | --- |
| PROTO\_VERSION | 1 | protocol/constants.yaml |
| Uplink audio | 16 kHz mono Opus, 20 ms | constants.yaml |
| Downlink audio | 24 kHz mono Opus, 20 ms | constants.yaml |
| Frame header | 12 bytes | constants.yaml |
| Hello timeout | 5 s | server config |
| Ping interval, server timeout | 10 s, 30 s | both |
| Reconnect backoff | 1 to 30 s, 20 percent jitter | firmware config.h |
| Pacer lead | 1000 ms | server config |
| Prebuffer | 200 ms | firmware config.h |
| Jitter buffer | 1.5 s | firmware config.h |
| Mic tail after speech | 300 ms | firmware config.h |
| Listen timeout (server) | 6 s | server config |
| Device-side LISTENING limit | 25 s | firmware config.h |
| FixedPolicy silence | 700 ms | server config |
| Max turn length | 20 s | server config |
| Tool timeout | 2 s | server config |
| History | 10 turns | server config |
| LLM max tokens | 150 | server config |

## Appendix B. Kickoff message for the coding agent

Copy this as the first message in a new agent session, with this document attached.

```
You are implementing the project described in ARCHITECTURE.md.
Read the whole document first, including the rules in section 0.
1. Summarise the architecture back to me in 10 lines and list anything unclear.
2. List the open items O1 to O6 and wait for my answers before Phase 2.
3. Start Phase 0. Work phase by phase. After each phase, show test output,
   update CHANGELOG.md, and stop for my review before the next phase.
4. Verify every library API against the installed version (section 12.2).
   Do not copy code from other projects. Ask before changing any locked decision.
```
