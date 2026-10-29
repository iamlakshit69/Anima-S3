"""
server/anima_server/transport/protocol.py — Protocol message models, parser, and frame codec.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional

from anima_server.transport.protocol_gen import (
    AudioFrame,
    FLAG_FIRST,
    FLAG_LAST,
    HEADER_SIZE,
    KIND_DOWN,
    KIND_UP,
    PROTO_VERSION,
)

log = logging.getLogger("anima.protocol")


# Device to Server messages
@dataclass
class AudioSettingsSpec:
    codec: str
    rate: int
    frame_ms: int


@dataclass
class AudioSpec:
    up: AudioSettingsSpec
    down: AudioSettingsSpec


@dataclass
class ToolSpec:
    name: str
    description: str
    params: Dict[str, Any]
    risk: Literal["safe", "confirm"] = "safe"


@dataclass
class Hello:
    type: str = "hello"
    proto: int = PROTO_VERSION
    device_id: str = ""
    fw: str = ""
    board: str = ""
    features: List[str] = None  # type: ignore
    audio: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    last_turn: int = 0


@dataclass
class ListenStart:
    turn: int
    reason: Literal["wake_word", "button", "barge_in"]
    type: str = "listen.start"
    wake_word: Optional[str] = None


@dataclass
class ListenEnd:
    turn: int
    type: str = "listen.end"


@dataclass
class Abort:
    turn: int
    type: str = "abort"


@dataclass
class ToolResultMsg:
    turn: int
    id: str
    ok: bool
    type: str = "tool.result"
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class PlaybackMsg:
    turn: int
    event: Literal["started", "finished", "underrun", "flushed"]
    buffered_ms: int = 0
    type: str = "playback"


@dataclass
class TelemetryMsg:
    state: str
    rssi: int
    heap_free: int
    psram_free: int
    uptime_s: int
    type: str = "telemetry"
    battery: Optional[int] = None


# Server to Device messages
@dataclass
class OtaOffer:
    version: str
    url: str
    sha256: str
    size: int


@dataclass
class HelloAck:
    proto: int
    session_id: str
    server: str
    listen_timeout_ms: int
    max_turn_ms: int
    type: str = "hello_ack"
    ota: Optional[OtaOffer] = None


@dataclass
class ListenStop:
    turn: int
    reason: Literal["endpoint", "no_speech", "max_len", "error"]
    type: str = "listen.stop"


@dataclass
class SttMsg:
    turn: int
    text: str
    type: str = "stt"


@dataclass
class ReplyMsg:
    turn: int
    text: str
    type: str = "reply"
    emotion: Optional[str] = None


@dataclass
class TtsStart:
    turn: int
    type: str = "tts.start"


@dataclass
class TtsStop:
    turn: int
    reason: Literal["done", "aborted", "error"]
    type: str = "tts.stop"


@dataclass
class ToolCallMsg:
    turn: int
    id: str
    name: str
    args: Dict[str, Any]
    timeout_ms: int
    type: str = "tool.call"


@dataclass
class AlertMsg:
    level: Literal["info", "warn", "error"]
    code: str
    text: str
    type: str = "alert"


@dataclass
class ErrorMsg:
    code: str
    text: str
    fatal: bool
    type: str = "error"


MESSAGE_TYPE_MAP = {
    "hello": Hello,
    "listen.start": ListenStart,
    "listen.end": ListenEnd,
    "abort": Abort,
    "tool.result": ToolResultMsg,
    "playback": PlaybackMsg,
    "telemetry": TelemetryMsg,
    "hello_ack": HelloAck,
    "listen.stop": ListenStop,
    "stt": SttMsg,
    "reply": ReplyMsg,
    "tts.start": TtsStart,
    "tts.stop": TtsStop,
    "tool.call": ToolCallMsg,
    "alert": AlertMsg,
    "error": ErrorMsg,
}


def parse_message(raw: str | dict) -> Any:
    """Parses a JSON message string or dictionary into a message dataclass or dict."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    msg_type = data.get("type")
    cls = MESSAGE_TYPE_MAP.get(msg_type)
    if cls is not None:
        try:
            # Filter kwargs to matching dataclass fields
            fields = cls.__dataclass_fields__.keys()
            filtered = {k: v for k, v in data.items() if k in fields}
            return cls(**filtered)
        except Exception as e:
            log.warning("Failed to parse known message %s: %s", msg_type, e)
    return data


def decode_frame(raw: bytes) -> Optional[AudioFrame]:
    """Decodes binary Opus frame with 12-byte header. Returns None if invalid."""
    try:
        return AudioFrame.decode(raw)
    except Exception as e:
        log.warning("Malformed binary frame (%d bytes): %s", len(raw), e)
        return None

