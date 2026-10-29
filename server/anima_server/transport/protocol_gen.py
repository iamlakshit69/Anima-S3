# THIS FILE IS AUTO-GENERATED — DO NOT EDIT BY HAND.
# Source: protocol/constants.yaml
# Generator: protocol/gen.py
# Generated: 2026-10-29T13:36:40Z
#
# R6 (Notes for agents.md): Generated files are never edited by hand.
#     Change protocol/constants.yaml and run `python protocol/gen.py`.

from __future__ import annotations

import struct
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------
PROTO_VERSION: int = 1

# ---------------------------------------------------------------------------
# Frame header constants
# ---------------------------------------------------------------------------
HEADER_SIZE: int = 12
KIND_UP: int = 0x01   # audio uplink  (device → server)
KIND_DOWN: int = 0x02  # audio downlink (server → device)
FLAG_FIRST: int = 0x01  # bit0: first frame of this turn stream
FLAG_LAST: int  = 0x02  # bit1: last frame of this turn stream

# ---------------------------------------------------------------------------
# Audio settings
# ---------------------------------------------------------------------------
UPLINK_RATE: int            = 16000
UPLINK_CHANNELS: int        = 1
UPLINK_FRAME_MS: int        = 20
UPLINK_SAMPLES_PER_FRAME: int = 320
UPLINK_CODEC: str           = "opus"
UPLINK_BITRATE_MIN: int     = 16000
UPLINK_BITRATE_MAX: int     = 24000
DOWNLINK_RATE: int            = 24000
DOWNLINK_CHANNELS: int        = 1
DOWNLINK_FRAME_MS: int        = 20
DOWNLINK_SAMPLES_PER_FRAME: int = 480
DOWNLINK_CODEC: str           = "opus"
DOWNLINK_BITRATE_MIN: int     = 24000
DOWNLINK_BITRATE_MAX: int     = 32000

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
HELLO_TIMEOUT_S: int   = 5
PING_INTERVAL_S: int   = 10
SERVER_TIMEOUT_S: int  = 30

# ---------------------------------------------------------------------------
# Reconnect backoff
# ---------------------------------------------------------------------------
RECONNECT_BACKOFF_S: list[int] = [1, 2, 4, 8, 16, 30]
RECONNECT_MAX_S: int           = 30
RECONNECT_JITTER: float        = 0.2

# ---------------------------------------------------------------------------
# Server-side operational constants
# ---------------------------------------------------------------------------
PACER_LEAD_MS: int         = 1000
LISTEN_TIMEOUT_MS: int     = 6000
MAX_TURN_MS: int           = 20000
FIXED_SILENCE_MS: int      = 700
SILENCE_MAX_MS: int        = 1100
TOOL_TIMEOUT_MS: int       = 2000
HISTORY_TURNS: int         = 10
LLM_MAX_TOKENS: int        = 150
MAX_SESSIONS: int          = 2

# ---------------------------------------------------------------------------
# Firmware-side operational constants (mirrored here for tooling/tests)
# ---------------------------------------------------------------------------
PREBUFFER_MS: int          = 200
JITTER_BUFFER_MS: int      = 1500
MIC_TAIL_MS: int           = 300
LISTENING_LIMIT_S: int     = 25


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------
E_PROTO_VERSION = "E_PROTO_VERSION"
E_AUTH = "E_AUTH"
E_BAD_FRAME = "E_BAD_FRAME"
E_STT_FAIL = "E_STT_FAIL"
E_LLM_FAIL = "E_LLM_FAIL"
E_TTS_FAIL = "E_TTS_FAIL"
E_TOOL_DENIED = "E_TOOL_DENIED"
E_TOOL_TIMEOUT = "E_TOOL_TIMEOUT"
E_BUSY = "E_BUSY"
E_INTERNAL = "E_INTERNAL"


# ---------------------------------------------------------------------------
# Message type string constants
# ---------------------------------------------------------------------------

# device to server
MSG_HELLO = "hello"
MSG_LISTEN_START = "listen.start"
MSG_LISTEN_END = "listen.end"
MSG_ABORT = "abort"
MSG_TOOL_RESULT = "tool.result"
MSG_PLAYBACK = "playback"
MSG_TELEMETRY = "telemetry"

# server to device
MSG_HELLO_ACK = "hello_ack"
MSG_LISTEN_STOP = "listen.stop"
MSG_STT = "stt"
MSG_REPLY = "reply"
MSG_TTS_START = "tts.start"
MSG_TTS_STOP = "tts.stop"
MSG_TOOL_CALL = "tool.call"
MSG_ALERT = "alert"
MSG_ERROR = "error"


# ---------------------------------------------------------------------------
# Binary audio frame
# ---------------------------------------------------------------------------
# Wire layout (little-endian, 12-byte header):
#   offset  size  type  field
#   0       1     u8    kind    KIND_UP=0x01  KIND_DOWN=0x02
#   1       1     u8    flags   bit0=FLAG_FIRST  bit1=FLAG_LAST
#   2       2     u16   seq     per-direction frame counter, wraps at 2^16
#   4       4     u32   turn    turn id
#   8       4     u32   t_ms    sender timestamp ms
#   12      n     bytes opus    one Opus packet

# Module-level struct (avoids ClassVar issues when loaded via importlib)
_FRAME_STRUCT: struct.Struct = struct.Struct("<BBHII")  # kind(u8) flags(u8) seq(u16) turn(u32) t_ms(u32)


@dataclass
class AudioFrame:
    """One binary WebSocket message carrying a single Opus packet."""

    kind: int    # KIND_UP or KIND_DOWN
    flags: int   # FLAG_FIRST | FLAG_LAST bitmask
    seq: int     # u16, wraps
    turn: int    # u32
    t_ms: int    # u32, sender timestamp ms
    opus: bytes  # raw Opus packet bytes

    def encode(self) -> bytes:
        """Encode to the 12-byte header followed by the Opus payload."""
        return _FRAME_STRUCT.pack(self.kind, self.flags, self.seq, self.turn, self.t_ms) + self.opus

    @classmethod
    def decode(cls, data: bytes) -> "AudioFrame":
        """Decode from raw bytes; raises ValueError on invalid input."""
        if len(data) < HEADER_SIZE:
            raise ValueError(
                f"Frame too short: {len(data)} bytes (minimum {HEADER_SIZE})"
            )
        kind, flags, seq, turn, t_ms = _FRAME_STRUCT.unpack(data[:HEADER_SIZE])
        if kind not in (KIND_UP, KIND_DOWN):
            raise ValueError(f"Unknown frame kind: 0x{kind:02X}")
        opus = data[HEADER_SIZE:]
        return cls(kind=kind, flags=flags, seq=seq, turn=turn, t_ms=t_ms, opus=opus)

    @property
    def is_first(self) -> bool:
        return bool(self.flags & FLAG_FIRST)

    @property
    def is_last(self) -> bool:
        return bool(self.flags & FLAG_LAST)
