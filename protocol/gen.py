#!/usr/bin/env python3
"""
protocol/gen.py — ANIMA-S3 protocol code generator.

Reads  protocol/constants.yaml  and generates:
  server/anima_server/transport/protocol_gen.py   (Python constants + AudioFrame codec)
  firmware/main/net/protocol_gen.h                (C header with #define constants + AnimaFrame struct)

R6: The generated files must NEVER be edited by hand. Change protocol/constants.yaml and re-run this script.
R4: All constants come from this single source; no magic numbers elsewhere.

Usage (from the repo root):
    python protocol/gen.py
"""

from __future__ import annotations

import pathlib
import struct
import sys
import textwrap
from datetime import datetime, timezone

import yaml

# ---------------------------------------------------------------------------
# Paths (all relative to the repo root, which is this file's parent-parent)
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
CONSTANTS_YAML = REPO_ROOT / "protocol" / "constants.yaml"
PY_OUT = REPO_ROOT / "server" / "anima_server" / "transport" / "protocol_gen.py"
C_OUT = REPO_ROOT / "firmware" / "main" / "net" / "protocol_gen.h"


# ---------------------------------------------------------------------------
# Load and validate the constants YAML
# ---------------------------------------------------------------------------

def load_constants() -> dict:
    with CONSTANTS_YAML.open() as fh:
        data = yaml.safe_load(fh)

    # Sanity-check a few critical values to catch accidental edits early.
    assert data["protocol"]["version"] >= 1, "PROTO_VERSION must be >= 1"
    hdr = data["frame"]["header_size"]
    assert hdr == 12, f"header_size must be 12 (got {hdr})"
    up = data["audio"]["uplink"]
    assert up["samples_per_frame"] == up["rate"] * up["frame_ms"] // 1000, \
        "uplink samples_per_frame mismatch"
    dn = data["audio"]["downlink"]
    assert dn["samples_per_frame"] == dn["rate"] * dn["frame_ms"] // 1000, \
        "downlink samples_per_frame mismatch"
    return data


# ---------------------------------------------------------------------------
# Generate Python output
# ---------------------------------------------------------------------------

PYTHON_HEADER = """\
# THIS FILE IS AUTO-GENERATED — DO NOT EDIT BY HAND.
# Source: protocol/constants.yaml
# Generator: protocol/gen.py
# Generated: {ts}
#
# R6 (Notes for agents.md): Generated files are never edited by hand.
#     Change protocol/constants.yaml and run `python protocol/gen.py`.

from __future__ import annotations

import struct
from dataclasses import dataclass

"""

PYTHON_AUDIO_FRAME = '''
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
'''


def _py_error_codes(codes: list[str]) -> str:
    lines = ["\n# ---------------------------------------------------------------------------",
             "# Error code constants",
             "# ---------------------------------------------------------------------------"]
    for code in codes:
        lines.append(f'{code} = "{code}"')
    return "\n".join(lines) + "\n"


def _py_message_types(msg: dict) -> str:
    lines = ["\n# ---------------------------------------------------------------------------",
             "# Message type string constants",
             "# ---------------------------------------------------------------------------"]
    for direction, types in msg.items():
        lines.append(f"\n# {direction.replace('_', ' ')}")
        for t in types:
            const_name = "MSG_" + t.upper().replace(".", "_")
            lines.append(f'{const_name} = "{t}"')
    return "\n".join(lines) + "\n"


def generate_python(data: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = [PYTHON_HEADER.format(ts=ts)]

    proto = data["protocol"]
    frame = data["frame"]
    audio = data["audio"]
    timing = data["timing"]
    reconnect = data["reconnect"]
    server = data["server"]
    firmware = data["firmware"]

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Protocol version")
    out.append("# ---------------------------------------------------------------------------")
    out.append(f'PROTO_VERSION: int = {proto["version"]}')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Frame header constants")
    out.append("# ---------------------------------------------------------------------------")
    out.append(f'HEADER_SIZE: int = {frame["header_size"]}')
    out.append(f'KIND_UP: int = 0x{frame["kind_up"]:02X}   # audio uplink  (device → server)')
    out.append(f'KIND_DOWN: int = 0x{frame["kind_down"]:02X}  # audio downlink (server → device)')
    out.append(f'FLAG_FIRST: int = 0x{frame["flag_first"]:02X}  # bit0: first frame of this turn stream')
    out.append(f'FLAG_LAST: int  = 0x{frame["flag_last"]:02X}  # bit1: last frame of this turn stream')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Audio settings")
    out.append("# ---------------------------------------------------------------------------")
    up = audio["uplink"]
    dn = audio["downlink"]
    out.append(f'UPLINK_RATE: int            = {up["rate"]}')
    out.append(f'UPLINK_CHANNELS: int        = {up["channels"]}')
    out.append(f'UPLINK_FRAME_MS: int        = {up["frame_ms"]}')
    out.append(f'UPLINK_SAMPLES_PER_FRAME: int = {up["samples_per_frame"]}')
    out.append(f'UPLINK_CODEC: str           = "{up["codec"]}"')
    out.append(f'UPLINK_BITRATE_MIN: int     = {up["bitrate_min"]}')
    out.append(f'UPLINK_BITRATE_MAX: int     = {up["bitrate_max"]}')
    out.append(f'DOWNLINK_RATE: int            = {dn["rate"]}')
    out.append(f'DOWNLINK_CHANNELS: int        = {dn["channels"]}')
    out.append(f'DOWNLINK_FRAME_MS: int        = {dn["frame_ms"]}')
    out.append(f'DOWNLINK_SAMPLES_PER_FRAME: int = {dn["samples_per_frame"]}')
    out.append(f'DOWNLINK_CODEC: str           = "{dn["codec"]}"')
    out.append(f'DOWNLINK_BITRATE_MIN: int     = {dn["bitrate_min"]}')
    out.append(f'DOWNLINK_BITRATE_MAX: int     = {dn["bitrate_max"]}')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Timing constants")
    out.append("# ---------------------------------------------------------------------------")
    out.append(f'HELLO_TIMEOUT_S: int   = {timing["hello_timeout_s"]}')
    out.append(f'PING_INTERVAL_S: int   = {timing["ping_interval_s"]}')
    out.append(f'SERVER_TIMEOUT_S: int  = {timing["server_timeout_s"]}')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Reconnect backoff")
    out.append("# ---------------------------------------------------------------------------")
    steps = reconnect["backoff_steps_s"]
    out.append(f'RECONNECT_BACKOFF_S: list[int] = {steps}')
    out.append(f'RECONNECT_MAX_S: int           = {reconnect["backoff_max_s"]}')
    out.append(f'RECONNECT_JITTER: float        = {reconnect["jitter_frac"]}')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Server-side operational constants")
    out.append("# ---------------------------------------------------------------------------")
    out.append(f'PACER_LEAD_MS: int         = {server["pacer_lead_ms"]}')
    out.append(f'LISTEN_TIMEOUT_MS: int     = {server["listen_timeout_ms"]}')
    out.append(f'MAX_TURN_MS: int           = {server["max_turn_ms"]}')
    out.append(f'FIXED_SILENCE_MS: int      = {server["fixed_silence_ms"]}')
    out.append(f'SILENCE_MAX_MS: int        = {server["silence_max_ms"]}')
    out.append(f'TOOL_TIMEOUT_MS: int       = {server["tool_timeout_ms"]}')
    out.append(f'HISTORY_TURNS: int         = {server["history_turns"]}')
    out.append(f'LLM_MAX_TOKENS: int        = {server["llm_max_tokens"]}')
    out.append(f'MAX_SESSIONS: int          = {server["max_sessions"]}')
    out.append("")

    out.append("# ---------------------------------------------------------------------------")
    out.append("# Firmware-side operational constants (mirrored here for tooling/tests)")
    out.append("# ---------------------------------------------------------------------------")
    out.append(f'PREBUFFER_MS: int          = {firmware["prebuffer_ms"]}')
    out.append(f'JITTER_BUFFER_MS: int      = {firmware["jitter_buffer_ms"]}')
    out.append(f'MIC_TAIL_MS: int           = {firmware["mic_tail_ms"]}')
    out.append(f'LISTENING_LIMIT_S: int     = {firmware["listening_limit_s"]}')
    out.append("")

    # Error codes
    out.append(_py_error_codes(data["error_codes"]))

    # Message types
    out.append(_py_message_types(data["message_types"]))

    # AudioFrame dataclass
    out.append(PYTHON_AUDIO_FRAME)

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Generate C header output
# ---------------------------------------------------------------------------

C_HEADER_TMPL = """\
/*
 * THIS FILE IS AUTO-GENERATED — DO NOT EDIT BY HAND.
 * Source: protocol/constants.yaml
 * Generator: protocol/gen.py
 * Generated: {ts}
 *
 * R6 (Notes for agents.md): Generated files are never edited by hand.
 *     Change protocol/constants.yaml and run `python protocol/gen.py`.
 */

#pragma once
#ifdef __cplusplus
extern "C" {{
#endif

#include <stdint.h>
#include <string.h>  /* memcpy */

/* --------------------------------------------------------------------------
 * Protocol version
 * -------------------------------------------------------------------------- */
#define ANIMA_PROTO_VERSION     {proto_version}U

/* --------------------------------------------------------------------------
 * Frame header constants
 * -------------------------------------------------------------------------- */
#define ANIMA_HEADER_SIZE       {header_size}U

#define ANIMA_KIND_UP           0x{kind_up:02X}U  /**< audio uplink: device -> server */
#define ANIMA_KIND_DOWN         0x{kind_down:02X}U  /**< audio downlink: server -> device */

#define ANIMA_FLAG_FIRST        0x{flag_first:02X}U  /**< bit 0: first frame of this turn stream */
#define ANIMA_FLAG_LAST         0x{flag_last:02X}U  /**< bit 1: last frame of this turn stream */

/* --------------------------------------------------------------------------
 * Audio settings
 * -------------------------------------------------------------------------- */
/* Uplink (device -> server): 16 kHz Opus mono, 20 ms frames */
#define ANIMA_UP_RATE               {up_rate}U
#define ANIMA_UP_CHANNELS           {up_channels}U
#define ANIMA_UP_FRAME_MS           {up_frame_ms}U
#define ANIMA_UP_SAMPLES_PER_FRAME  {up_spf}U
#define ANIMA_UP_BITRATE_MIN        {up_bmin}U
#define ANIMA_UP_BITRATE_MAX        {up_bmax}U

/* Downlink (server -> device): 24 kHz Opus mono, 20 ms frames */
#define ANIMA_DN_RATE               {dn_rate}U
#define ANIMA_DN_CHANNELS           {dn_channels}U
#define ANIMA_DN_FRAME_MS           {dn_frame_ms}U
#define ANIMA_DN_SAMPLES_PER_FRAME  {dn_spf}U
#define ANIMA_DN_BITRATE_MIN        {dn_bmin}U
#define ANIMA_DN_BITRATE_MAX        {dn_bmax}U

/* --------------------------------------------------------------------------
 * Timing constants
 * -------------------------------------------------------------------------- */
#define ANIMA_HELLO_TIMEOUT_S       {hello_timeout_s}U
#define ANIMA_PING_INTERVAL_S       {ping_interval_s}U
#define ANIMA_SERVER_TIMEOUT_S      {server_timeout_s}U

/* --------------------------------------------------------------------------
 * Reconnect backoff
 * -------------------------------------------------------------------------- */
#define ANIMA_RECONNECT_MAX_S       {reconnect_max_s}U
/* Steps in seconds: {reconnect_steps} */

/* --------------------------------------------------------------------------
 * Operational constants
 * -------------------------------------------------------------------------- */
#define ANIMA_PACER_LEAD_MS         {pacer_lead_ms}U
#define ANIMA_LISTEN_TIMEOUT_MS     {listen_timeout_ms}U
#define ANIMA_MAX_TURN_MS           {max_turn_ms}U
#define ANIMA_FIXED_SILENCE_MS      {fixed_silence_ms}U
#define ANIMA_SILENCE_MAX_MS        {silence_max_ms}U
#define ANIMA_TOOL_TIMEOUT_MS       {tool_timeout_ms}U
#define ANIMA_PREBUFFER_MS          {prebuffer_ms}U
#define ANIMA_JITTER_BUFFER_MS      {jitter_buffer_ms}U
#define ANIMA_MIC_TAIL_MS           {mic_tail_ms}U
#define ANIMA_LISTENING_LIMIT_S     {listening_limit_s}U

/* --------------------------------------------------------------------------
 * Binary frame header struct (little-endian, packed, 12 bytes)
 *
 * Wire layout:
 *   offset  size  type   field
 *   0       1     u8     kind    (ANIMA_KIND_UP / ANIMA_KIND_DOWN)
 *   1       1     u8     flags   bit0=ANIMA_FLAG_FIRST, bit1=ANIMA_FLAG_LAST
 *   2       2     u16le  seq     per-direction frame counter, wraps at 2^16
 *   4       4     u32le  turn    turn id
 *   8       4     u32le  t_ms    sender timestamp ms
 *   12      n     bytes  opus    one Opus packet
 * -------------------------------------------------------------------------- */
#pragma pack(push, 1)
typedef struct {{
    uint8_t  kind;    /**< ANIMA_KIND_UP or ANIMA_KIND_DOWN */
    uint8_t  flags;   /**< FLAG_FIRST | FLAG_LAST bitmask */
    uint16_t seq;     /**< little-endian, per-direction counter */
    uint32_t turn;    /**< little-endian, turn id */
    uint32_t t_ms;    /**< little-endian, sender timestamp ms */
    /* opus payload follows immediately in the WebSocket binary message */
}} AnimaFrameHeader;
#pragma pack(pop)

/** Minimum valid frame length (header only, no Opus payload). */
#define ANIMA_FRAME_MIN_LEN  sizeof(AnimaFrameHeader)

/* --------------------------------------------------------------------------
 * Inline helpers — encode and decode the 12-byte header.
 * The device is little-endian (ESP32), so plain struct access is correct.
 * -------------------------------------------------------------------------- */

/**
 * @brief Fill @p hdr from the raw @p data bytes received over WebSocket.
 * @return 1 on success, 0 if @p len is too short or kind is unknown.
 */
static inline int anima_frame_decode(const uint8_t *data, size_t len,
                                      AnimaFrameHeader *hdr)
{{
    if (len < sizeof(AnimaFrameHeader)) return 0;
    memcpy(hdr, data, sizeof(AnimaFrameHeader));
    /* ESP32 is little-endian; host tests on x86 are also little-endian.
     * If porting to a big-endian host, byte-swap seq, turn and t_ms here. */
    if (hdr->kind != ANIMA_KIND_UP && hdr->kind != ANIMA_KIND_DOWN) return 0;
    return 1;
}}

/**
 * @brief Write the 12-byte header into @p buf (which must be at least 12 bytes).
 */
static inline void anima_frame_encode(uint8_t *buf, uint8_t kind, uint8_t flags,
                                       uint16_t seq, uint32_t turn, uint32_t t_ms)
{{
    AnimaFrameHeader hdr;
    hdr.kind  = kind;
    hdr.flags = flags;
    hdr.seq   = seq;
    hdr.turn  = turn;
    hdr.t_ms  = t_ms;
    memcpy(buf, &hdr, sizeof(hdr));
}}

/* --------------------------------------------------------------------------
 * Error code string constants
 * -------------------------------------------------------------------------- */
{error_defines}

/* --------------------------------------------------------------------------
 * Message type string constants
 * -------------------------------------------------------------------------- */
{msg_defines}

#ifdef __cplusplus
}} /* extern "C" */
#endif
"""


def _c_error_defines(codes: list[str]) -> str:
    lines = []
    for code in codes:
        macro = f"ANIMA_ERR_{code}"
        lines.append(f'#define {macro:<32} "{code}"')
    return "\n".join(lines)


def _c_msg_defines(msg: dict) -> str:
    lines = []
    for direction, types in msg.items():
        lines.append(f"/* {direction.replace('_', ' ')} */")
        for t in types:
            macro = "ANIMA_MSG_" + t.upper().replace(".", "_")
            lines.append(f'#define {macro:<32} "{t}"')
        lines.append("")
    return "\n".join(lines)


def generate_c_header(data: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proto = data["protocol"]
    frame = data["frame"]
    audio = data["audio"]
    timing = data["timing"]
    reconnect = data["reconnect"]
    server = data["server"]
    firmware = data["firmware"]
    up = audio["uplink"]
    dn = audio["downlink"]

    return C_HEADER_TMPL.format(
        ts=ts,
        proto_version=proto["version"],
        header_size=frame["header_size"],
        kind_up=frame["kind_up"],
        kind_down=frame["kind_down"],
        flag_first=frame["flag_first"],
        flag_last=frame["flag_last"],
        up_rate=up["rate"],
        up_channels=up["channels"],
        up_frame_ms=up["frame_ms"],
        up_spf=up["samples_per_frame"],
        up_bmin=up["bitrate_min"],
        up_bmax=up["bitrate_max"],
        dn_rate=dn["rate"],
        dn_channels=dn["channels"],
        dn_frame_ms=dn["frame_ms"],
        dn_spf=dn["samples_per_frame"],
        dn_bmin=dn["bitrate_min"],
        dn_bmax=dn["bitrate_max"],
        hello_timeout_s=timing["hello_timeout_s"],
        ping_interval_s=timing["ping_interval_s"],
        server_timeout_s=timing["server_timeout_s"],
        reconnect_max_s=reconnect["backoff_max_s"],
        reconnect_steps=reconnect["backoff_steps_s"],
        pacer_lead_ms=server["pacer_lead_ms"],
        listen_timeout_ms=server["listen_timeout_ms"],
        max_turn_ms=server["max_turn_ms"],
        fixed_silence_ms=server["fixed_silence_ms"],
        silence_max_ms=server["silence_max_ms"],
        tool_timeout_ms=server["tool_timeout_ms"],
        prebuffer_ms=firmware["prebuffer_ms"],
        jitter_buffer_ms=firmware["jitter_buffer_ms"],
        mic_tail_ms=firmware["mic_tail_ms"],
        listening_limit_s=firmware["listening_limit_s"],
        error_defines=_c_error_defines(data["error_codes"]),
        msg_defines=_c_msg_defines(data["message_types"]),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("ANIMA-S3 protocol generator")
    print(f"  Reading  : {CONSTANTS_YAML}")

    data = load_constants()

    # Write Python
    py_content = generate_python(data)
    PY_OUT.parent.mkdir(parents=True, exist_ok=True)
    PY_OUT.write_text(py_content, encoding="utf-8")
    print(f"  Wrote    : {PY_OUT}")

    # Write C header
    c_content = generate_c_header(data)
    C_OUT.parent.mkdir(parents=True, exist_ok=True)
    C_OUT.write_text(c_content, encoding="utf-8")
    print(f"  Wrote    : {C_OUT}")

    # Quick self-check: import the generated Python module to catch syntax errors.
    import importlib.util
    import sys as _sys
    spec = importlib.util.spec_from_file_location("protocol_gen", PY_OUT)
    mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    _sys.modules["protocol_gen"] = mod             # register so ClassVar resolves correctly
    spec.loader.exec_module(mod)                   # type: ignore[union-attr]
    assert mod.PROTO_VERSION == data["protocol"]["version"]
    assert mod.HEADER_SIZE == data["frame"]["header_size"]
    assert mod.KIND_UP == data["frame"]["kind_up"]
    assert mod.KIND_DOWN == data["frame"]["kind_down"]
    print("  Self-check: Python module imports and constants match — OK")
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
