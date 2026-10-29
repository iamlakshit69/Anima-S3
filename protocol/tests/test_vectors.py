"""
protocol/tests/test_vectors.py — Round-trip tests for the ANIMA-S3 wire protocol.

What this file does (per Phase 0 acceptance criteria):
  1. Calls gen.py first (subprocess) to regenerate protocol_gen.py and protocol_gen.h.
  2. Imports the generated protocol_gen.py and verifies every constant matches constants.yaml.
  3. Parses every frame/message in vectors.json and asserts round-trip integrity.
  4. Tests encode → decode round-trips for AudioFrame.
  5. Tests that a frame with wrong size raises ValueError.

R16: Do not claim something works unless a test or a run showed it.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import types

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
GEN_PY = REPO_ROOT / "protocol" / "gen.py"
CONSTANTS_YAML = REPO_ROOT / "protocol" / "constants.yaml"
VECTORS_JSON = REPO_ROOT / "protocol" / "vectors.json"
PROTOCOL_GEN_PY = REPO_ROOT / "server" / "anima_server" / "transport" / "protocol_gen.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_protocol_gen() -> types.ModuleType:
    """Load the generated protocol_gen.py as a module."""
    spec = importlib.util.spec_from_file_location("protocol_gen", PROTOCOL_GEN_PY)
    assert spec is not None, f"Cannot find {PROTOCOL_GEN_PY}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["protocol_gen"] = mod  # register so dataclass ClassVar annotations resolve
    spec.loader.exec_module(mod)       # type: ignore[union-attr]
    return mod


def _parse_hex(hex_str: str) -> bytes:
    """Parse a hex string with optional spaces into bytes."""
    return bytes.fromhex(hex_str.replace(" ", ""))


# ---------------------------------------------------------------------------
# Step 1 — regenerate outputs
# ---------------------------------------------------------------------------

class TestGenPy:
    def test_gen_runs_without_error(self) -> None:
        """gen.py must run cleanly from the repo root."""
        result = subprocess.run(
            [sys.executable, str(GEN_PY)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"gen.py exited with code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "Done." in result.stdout

    def test_generated_py_exists(self) -> None:
        assert PROTOCOL_GEN_PY.exists(), f"Missing {PROTOCOL_GEN_PY}"

    def test_generated_c_header_exists(self) -> None:
        c_out = REPO_ROOT / "firmware" / "main" / "net" / "protocol_gen.h"
        assert c_out.exists(), f"Missing {c_out}"


# ---------------------------------------------------------------------------
# Step 2 — constants match between constants.yaml and protocol_gen.py
# ---------------------------------------------------------------------------

class TestConstantsMatch:
    @pytest.fixture(scope="class")
    @classmethod
    def constants(cls) -> dict:
        with CONSTANTS_YAML.open() as fh:
            return yaml.safe_load(fh)

    @pytest.fixture(scope="class")
    @classmethod
    def pg(cls) -> types.ModuleType:
        return _load_protocol_gen()

    def test_proto_version(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.PROTO_VERSION == constants["protocol"]["version"]

    def test_header_size(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.HEADER_SIZE == constants["frame"]["header_size"]

    def test_kind_up(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.KIND_UP == constants["frame"]["kind_up"]

    def test_kind_down(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.KIND_DOWN == constants["frame"]["kind_down"]

    def test_flag_first(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.FLAG_FIRST == constants["frame"]["flag_first"]

    def test_flag_last(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.FLAG_LAST == constants["frame"]["flag_last"]

    def test_uplink_rate(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.UPLINK_RATE == constants["audio"]["uplink"]["rate"]

    def test_uplink_channels(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.UPLINK_CHANNELS == constants["audio"]["uplink"]["channels"]

    def test_uplink_frame_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.UPLINK_FRAME_MS == constants["audio"]["uplink"]["frame_ms"]

    def test_uplink_samples_per_frame(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.UPLINK_SAMPLES_PER_FRAME == constants["audio"]["uplink"]["samples_per_frame"]

    def test_downlink_rate(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.DOWNLINK_RATE == constants["audio"]["downlink"]["rate"]

    def test_downlink_samples_per_frame(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.DOWNLINK_SAMPLES_PER_FRAME == constants["audio"]["downlink"]["samples_per_frame"]

    def test_hello_timeout_s(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.HELLO_TIMEOUT_S == constants["timing"]["hello_timeout_s"]

    def test_ping_interval_s(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.PING_INTERVAL_S == constants["timing"]["ping_interval_s"]

    def test_server_timeout_s(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.SERVER_TIMEOUT_S == constants["timing"]["server_timeout_s"]

    def test_reconnect_max_s(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.RECONNECT_MAX_S == constants["reconnect"]["backoff_max_s"]

    def test_reconnect_backoff_steps(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.RECONNECT_BACKOFF_S == constants["reconnect"]["backoff_steps_s"]

    def test_pacer_lead_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.PACER_LEAD_MS == constants["server"]["pacer_lead_ms"]

    def test_listen_timeout_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.LISTEN_TIMEOUT_MS == constants["server"]["listen_timeout_ms"]

    def test_max_turn_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.MAX_TURN_MS == constants["server"]["max_turn_ms"]

    def test_fixed_silence_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.FIXED_SILENCE_MS == constants["server"]["fixed_silence_ms"]

    def test_tool_timeout_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.TOOL_TIMEOUT_MS == constants["server"]["tool_timeout_ms"]

    def test_history_turns(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.HISTORY_TURNS == constants["server"]["history_turns"]

    def test_llm_max_tokens(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.LLM_MAX_TOKENS == constants["server"]["llm_max_tokens"]

    def test_prebuffer_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.PREBUFFER_MS == constants["firmware"]["prebuffer_ms"]

    def test_jitter_buffer_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.JITTER_BUFFER_MS == constants["firmware"]["jitter_buffer_ms"]

    def test_mic_tail_ms(self, constants: dict, pg: types.ModuleType) -> None:
        assert pg.MIC_TAIL_MS == constants["firmware"]["mic_tail_ms"]

    def test_error_code_constants(self, constants: dict, pg: types.ModuleType) -> None:
        for code in constants["error_codes"]:
            assert hasattr(pg, code), f"Missing error code constant: {code}"
            assert getattr(pg, code) == code

    def test_message_type_constants(self, constants: dict, pg: types.ModuleType) -> None:
        for direction, types_list in constants["message_types"].items():
            for t in types_list:
                const_name = "MSG_" + t.upper().replace(".", "_")
                assert hasattr(pg, const_name), f"Missing message type constant: {const_name}"
                assert getattr(pg, const_name) == t


# ---------------------------------------------------------------------------
# Step 3 — vectors.json round-trip tests
# ---------------------------------------------------------------------------

class TestVectors:
    @pytest.fixture(scope="class")
    @classmethod
    def vectors(cls) -> list[dict]:
        with VECTORS_JSON.open() as fh:
            data = json.load(fh)
        return data["vectors"]

    @pytest.fixture(scope="class")
    @classmethod
    def pg(cls) -> types.ModuleType:
        return _load_protocol_gen()

    # --- binary frame vectors ---

    def _check_binary_vector(self, v: dict, pg: types.ModuleType) -> None:
        """Decode a binary frame vector and assert all expected fields."""
        raw = _parse_hex(v["hex"])
        frame = pg.AudioFrame.decode(raw)
        exp = v["expected"]

        assert frame.kind == exp["kind"], f"[{v['id']}] kind mismatch"
        assert frame.flags == exp["flags"], f"[{v['id']}] flags mismatch"
        assert frame.seq == exp["seq"], f"[{v['id']}] seq mismatch"
        assert frame.turn == exp["turn"], f"[{v['id']}] turn mismatch"
        assert frame.t_ms == exp["t_ms"], f"[{v['id']}] t_ms mismatch"
        assert len(frame.opus) == exp["opus_len"], f"[{v['id']}] opus length mismatch"
        assert frame.opus.hex().upper() == exp["opus_hex"], f"[{v['id']}] opus bytes mismatch"

    def test_uplink_plain(self, vectors: list[dict], pg: types.ModuleType) -> None:
        v = next(x for x in vectors if x["id"] == "uplink_plain")
        self._check_binary_vector(v, pg)

    def test_uplink_first_flag(self, vectors: list[dict], pg: types.ModuleType) -> None:
        v = next(x for x in vectors if x["id"] == "uplink_first")
        self._check_binary_vector(v, pg)
        raw = _parse_hex(v["hex"])
        frame = pg.AudioFrame.decode(raw)
        assert frame.is_first
        assert not frame.is_last

    def test_uplink_last_flag(self, vectors: list[dict], pg: types.ModuleType) -> None:
        v = next(x for x in vectors if x["id"] == "uplink_last")
        self._check_binary_vector(v, pg)
        raw = _parse_hex(v["hex"])
        frame = pg.AudioFrame.decode(raw)
        assert not frame.is_first
        assert frame.is_last

    def test_uplink_first_and_last(self, vectors: list[dict], pg: types.ModuleType) -> None:
        v = next(x for x in vectors if x["id"] == "uplink_first_and_last")
        self._check_binary_vector(v, pg)
        raw = _parse_hex(v["hex"])
        frame = pg.AudioFrame.decode(raw)
        assert frame.is_first
        assert frame.is_last

    def test_downlink_plain(self, vectors: list[dict], pg: types.ModuleType) -> None:
        v = next(x for x in vectors if x["id"] == "downlink_plain")
        self._check_binary_vector(v, pg)
        raw = _parse_hex(v["hex"])
        frame = pg.AudioFrame.decode(raw)
        assert frame.kind == pg.KIND_DOWN

    def test_all_binary_vectors(self, vectors: list[dict], pg: types.ModuleType) -> None:
        """Smoke-test all binary frame vectors."""
        binary_vectors = [v for v in vectors if v["type"] == "binary_frame"]
        assert len(binary_vectors) >= 5, "Expected at least 5 binary frame vectors"
        for v in binary_vectors:
            self._check_binary_vector(v, pg)

    # --- JSON message vectors ---

    def _check_json_vector(self, v: dict) -> None:
        """Parse a JSON message vector and check expected key fields."""
        msg = v["json"]
        exp = v["expected"]

        assert msg["type"] == exp["type"], f"[{v['id']}] type mismatch"
        for key, val in exp.items():
            assert key in msg, f"[{v['id']}] missing expected key '{key}'"
            assert msg[key] == val, f"[{v['id']}] field '{key}': expected {val!r}, got {msg[key]!r}"

    def test_all_json_vectors(self, vectors: list[dict]) -> None:
        """All JSON message vectors must parse and satisfy their expected assertions."""
        json_vectors = [v for v in vectors if v["type"] == "json_message"]
        # Ensure we have one of each required message type
        types_present = {v["json"]["type"] for v in json_vectors}
        required = {
            "hello", "hello_ack", "listen.start", "listen.end", "listen.stop",
            "abort", "tool.result", "playback", "telemetry", "stt", "reply",
            "tts.start", "tts.stop", "tool.call", "alert", "error",
        }
        missing = required - types_present
        assert not missing, f"Missing JSON message type vectors: {missing}"

        for v in json_vectors:
            self._check_json_vector(v)

    def test_json_roundtrip_is_json_serializable(self, vectors: list[dict]) -> None:
        """Every JSON vector must survive a json.dumps → json.loads round-trip."""
        for v in [x for x in vectors if x["type"] == "json_message"]:
            serialized = json.dumps(v["json"])
            deserialized = json.loads(serialized)
            assert deserialized == v["json"], f"[{v['id']}] JSON round-trip failed"


# ---------------------------------------------------------------------------
# Step 4 — encode → decode round-trips for AudioFrame
# ---------------------------------------------------------------------------

class TestAudioFrameRoundTrip:
    @pytest.fixture(scope="class")
    @classmethod
    def pg(cls) -> types.ModuleType:
        return _load_protocol_gen()

    def _roundtrip(self, pg: types.ModuleType, **kwargs) -> None:
        frame = pg.AudioFrame(**kwargs)
        encoded = frame.encode()
        decoded = pg.AudioFrame.decode(encoded)
        assert decoded.kind == frame.kind
        assert decoded.flags == frame.flags
        assert decoded.seq == frame.seq
        assert decoded.turn == frame.turn
        assert decoded.t_ms == frame.t_ms
        assert decoded.opus == frame.opus

    def test_roundtrip_uplink(self, pg: types.ModuleType) -> None:
        self._roundtrip(pg,
                        kind=pg.KIND_UP, flags=pg.FLAG_FIRST, seq=0,
                        turn=1, t_ms=0, opus=b"\xDE\xAD\xBE\xEF")

    def test_roundtrip_downlink(self, pg: types.ModuleType) -> None:
        self._roundtrip(pg,
                        kind=pg.KIND_DOWN, flags=pg.FLAG_LAST, seq=1023,
                        turn=42, t_ms=20480, opus=b"\x01\x02\x03")

    def test_roundtrip_first_and_last(self, pg: types.ModuleType) -> None:
        flags = pg.FLAG_FIRST | pg.FLAG_LAST
        self._roundtrip(pg,
                        kind=pg.KIND_UP, flags=flags, seq=0,
                        turn=7, t_ms=20, opus=b"\xC0")

    def test_roundtrip_empty_opus(self, pg: types.ModuleType) -> None:
        """An AudioFrame with no Opus payload is unusual but must encode/decode cleanly."""
        self._roundtrip(pg,
                        kind=pg.KIND_UP, flags=0, seq=0,
                        turn=0, t_ms=0, opus=b"")

    def test_roundtrip_max_seq_and_turn(self, pg: types.ModuleType) -> None:
        """seq wraps at 2^16; turn is a u32. Check boundary values."""
        self._roundtrip(pg,
                        kind=pg.KIND_DOWN, flags=0, seq=0xFFFF,
                        turn=0xFFFFFFFF, t_ms=0xFFFFFFFF, opus=b"\x00")

    def test_encode_length(self, pg: types.ModuleType) -> None:
        opus_payload = b"\xDE\xAD\xBE\xEF"
        frame = pg.AudioFrame(kind=pg.KIND_UP, flags=0, seq=0, turn=0, t_ms=0, opus=opus_payload)
        encoded = frame.encode()
        assert len(encoded) == pg.HEADER_SIZE + len(opus_payload)

    def test_is_first_is_last_properties(self, pg: types.ModuleType) -> None:
        f_first = pg.AudioFrame(kind=pg.KIND_UP, flags=pg.FLAG_FIRST, seq=0, turn=1, t_ms=0, opus=b"\x00")
        assert f_first.is_first
        assert not f_first.is_last

        f_last = pg.AudioFrame(kind=pg.KIND_UP, flags=pg.FLAG_LAST, seq=1, turn=1, t_ms=20, opus=b"\x00")
        assert not f_last.is_first
        assert f_last.is_last

        f_both = pg.AudioFrame(kind=pg.KIND_UP, flags=pg.FLAG_FIRST | pg.FLAG_LAST, seq=0, turn=1, t_ms=0, opus=b"\x00")
        assert f_both.is_first
        assert f_both.is_last


# ---------------------------------------------------------------------------
# Step 5 — error cases
# ---------------------------------------------------------------------------

class TestErrorCases:
    @pytest.fixture(scope="class")
    @classmethod
    def pg(cls) -> types.ModuleType:
        return _load_protocol_gen()

    def test_frame_too_short_raises(self, pg: types.ModuleType) -> None:
        """A frame shorter than HEADER_SIZE must raise ValueError."""
        with pytest.raises(ValueError, match="too short"):
            pg.AudioFrame.decode(b"\x01\x00\x00\x00\x01\x00\x00\x00")  # only 8 bytes

    def test_empty_bytes_raises(self, pg: types.ModuleType) -> None:
        with pytest.raises(ValueError, match="too short"):
            pg.AudioFrame.decode(b"")

    def test_unknown_kind_raises(self, pg: types.ModuleType) -> None:
        """A frame with an unknown kind byte must raise ValueError."""
        import struct
        bad_frame = struct.pack("<BBHII", 0xFF, 0, 0, 1, 0) + b"\xDE\xAD"
        with pytest.raises(ValueError, match="[Uu]nknown frame kind"):
            pg.AudioFrame.decode(bad_frame)

    def test_exactly_header_size_no_opus(self, pg: types.ModuleType) -> None:
        """A frame of exactly HEADER_SIZE bytes is valid (empty Opus payload)."""
        import struct
        hdr = struct.pack("<BBHII", pg.KIND_UP, 0, 0, 1, 0)
        frame = pg.AudioFrame.decode(hdr)
        assert frame.opus == b""
        assert frame.kind == pg.KIND_UP
