"""
server/anima_server/transport/session.py — Session state, queues, reader loop, and turn authority.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from anima_server.audio.endpointer import Endpointer, FixedPolicy
from anima_server.audio.opus_codec import OpusDecoder, OpusEncoder
from anima_server.config import Config
from anima_server.core.metrics import SessionMetrics, TurnLatency
from anima_server.core.supervisor import supervise
from anima_server.core.turn import TurnScope
from anima_server.pipeline.egress import egress_stage
from anima_server.pipeline.ingest import ingest_stage
from anima_server.pipeline.llm import llm_stage
from anima_server.pipeline.stt import stt_stage
from anima_server.pipeline.tts import tts_stage
from anima_server.tools.registry import ToolRegistry
from anima_server.transport.protocol import (
    AlertMsg,
    ErrorMsg,
    Hello,
    ListenStop,
    TtsStop,
    decode_frame,
    parse_message,
)
from anima_server.transport.protocol_gen import KIND_UP

log = logging.getLogger("anima.session")


def put_drop_oldest(queue: asyncio.Queue, item: Any, counter_cb: Any = None) -> None:
    """Inserts into a bounded asyncio queue, dropping the oldest item if full."""
    if queue.full():
        try:
            queue.get_nowait()
            if counter_cb:
                counter_cb()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        pass


class Session:
    """Manages the lifecycle of an active device connection."""

    def __init__(
        self,
        device_id: str,
        ws: Any,
        cfg: Config,
        models: Any,
        provider: Any,
        hello: Hello,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.device_id = device_id
        self.ws = ws
        self.cfg = cfg
        self.models = models
        self.provider = provider
        self.hello = hello

        # State & Turn tracking
        self.current_turn = getattr(hello, "last_turn", 0)
        self.state = "IDLE"  # IDLE, LISTENING, PROCESSING, SPEAKING
        self.scope: Optional[TurnScope] = None
        self.metrics = SessionMetrics()
        self.latency = TurnLatency(turn=self.current_turn, session_id=self.id)
        self.history: List[Dict[str, Any]] = []
        self.telemetry: Optional[Dict[str, Any]] = None

        # Codecs
        try:
            self.decoder: Optional[OpusDecoder] = OpusDecoder(rate=cfg.up_rate, channels=1, frame_ms=cfg.frame_ms)
            self.encoder: Optional[OpusEncoder] = OpusEncoder(rate=cfg.down_rate, channels=1, frame_ms=cfg.frame_ms)
        except Exception as e:
            log.warning("Could not initialize Opus codecs: %s", e)
            self.decoder = None
            self.encoder = None

        # Bounded pipeline queues
        self.ingest_q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self.stt_q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self.llm_q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self.token_q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.phrase_q: asyncio.Queue = asyncio.Queue(maxsize=4)
        self.egress_q: asyncio.Queue = asyncio.Queue(maxsize=10)

        # Tools & Endpointer
        self.policy = FixedPolicy(cfg.fixed_silence_ms)
        self.endpointer: Optional[Endpointer] = None
        self.tools = ToolRegistry(cfg, self)
        if hello.tools:
            self.tools.register_device_tools(hello.tools)

        self._closed = False
        self._tasks: List[asyncio.Task] = []

    def is_stale(self, turn: int) -> bool:
        """Rule T3 & T5: checks if an item belongs to the active turn."""
        return turn != self.current_turn

    def begin_turn(self, turn: int, reason: str) -> None:
        """Starts a new conversation turn (Rule T1, T3)."""
        if turn <= self.current_turn:
            self.metrics.stale_listen_start += 1
            log.warning("Ignoring stale listen.start for turn %d (current=%d)", turn, self.current_turn)
            return

        log.info("Starting turn %d (reason=%s, prev=%d)", turn, reason, self.current_turn)
        if self.scope:
            self.scope.cancel()

        self.current_turn = turn
        self.scope = TurnScope(turn)
        self.drain_all_queues()

        if self.models and hasattr(self.models, "vad"):
            self.endpointer = Endpointer(self.cfg, self.models.vad, self.policy)
        self.latency = TurnLatency(turn=turn, session_id=self.id, listen_start=time.time())
        self.state = "LISTENING"

        # Watchdog for no-speech timeout if satellite sends no audio or silence
        async def _listen_timeout_watchdog(t: int):
            await asyncio.sleep(self.cfg.listen_timeout_ms / 1000.0)
            if not self.is_stale(t) and self.state == "LISTENING":
                # If speech already started (state is IN_SPEECH), do not trigger no_speech
                if self.endpointer is not None and getattr(self.endpointer, "state", 0) != 0:
                    return
                log.info("Turn %d listen timeout (no speech received within %dms)", t, self.cfg.listen_timeout_ms)
                await self.send(ListenStop(turn=t, reason="no_speech"))
                self.finish_turn(t, reason="no_speech")

        self.scope.spawn(_listen_timeout_watchdog(turn), name=f"listen-timeout-{turn}")

    def cancel_turn(self, reason: str = "aborted") -> None:
        """Cancels turn in progress (e.g. on abort or barge-in)."""
        log.info("Cancelling turn %d: %s", self.current_turn, reason)
        if self.scope:
            self.scope.cancel()
        self.drain_all_queues()
        self.state = "IDLE"

    def finish_turn(self, turn: int, reason: str = "done") -> None:
        """Finishes turn processing when speech is empty or completed."""
        if self.is_stale(turn):
            return
        log.info("Finishing turn %d (%s)", turn, reason)
        self.state = "IDLE"

    def endpointer_force_end(self, turn: int) -> None:
        """Forces end of speech on push-to-talk button release."""
        if self.is_stale(turn) or self.endpointer is None:
            return
        res = self.endpointer.force_end()
        self.state = "PROCESSING"
        self.latency.endpoint_at = time.time()
        asyncio.create_task(self.send(ListenStop(turn=turn, reason="endpoint")))
        if res.audio is not None and len(res.audio) > 0:
            put_drop_oldest(self.stt_q, (turn, res.audio))

    def drain_all_queues(self) -> None:
        """Empties all queues when starting a fresh turn."""
        for q in [self.ingest_q, self.stt_q, self.llm_q, self.token_q, self.phrase_q, self.egress_q]:
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def send(self, msg: Any) -> None:
        """Serializes and sends a JSON control message over WebSocket."""
        if self._closed:
            return
        if hasattr(msg, "__dataclass_fields__"):
            payload = asdict(msg)
        elif isinstance(msg, dict):
            payload = msg
        else:
            payload = {"type": str(msg)}
        try:
            await self.ws.send(json.dumps(payload))
        except Exception as e:
            log.warning("Failed to send WebSocket message: %s", e)

    async def send_raw_bytes(self, data: bytes) -> None:
        """Transmits raw binary audio frame over WebSocket."""
        if self._closed:
            return
        try:
            await self.ws.send(data)
        except Exception as e:
            log.warning("Failed to send binary audio: %s", e)

    async def send_alert(self, level: str, code: str, text: str) -> None:
        await self.send(AlertMsg(level=level, code=code, text=text))  # type: ignore

    async def send_error(self, code: str, text: str, fatal: bool = False) -> None:
        await self.send(ErrorMsg(code=code, text=text, fatal=fatal))

    def on_audio(self, raw: bytes) -> None:
        """Handles inbound binary audio frame from satellite."""
        frame = decode_frame(raw)
        if frame is None:
            self.metrics.bad_frames += 1
            return

        if frame.kind != KIND_UP or frame.turn != self.current_turn or self.state != "LISTENING":
            self.metrics.dropped_frames += 1
            return

        put_drop_oldest(
            self.ingest_q,
            (frame.turn, frame),
            lambda: self.metrics.inc_stale("ingest"),
        )

    def on_json(self, msg: Any) -> None:
        """Handles inbound JSON control message from satellite."""
        msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
        turn = getattr(msg, "turn", None) or (msg.get("turn") if isinstance(msg, dict) else None)

        if msg_type == "listen.start":
            reason = getattr(msg, "reason", "wake_word") or (msg.get("reason", "wake_word") if isinstance(msg, dict) else "wake_word")
            self.begin_turn(turn, reason)
        elif msg_type == "listen.end":
            self.endpointer_force_end(turn)
        elif msg_type == "abort":
            if turn == self.current_turn:
                self.cancel_turn("aborted")
        elif msg_type == "tool.result":
            call_id = getattr(msg, "id", None) or (msg.get("id") if isinstance(msg, dict) else None)
            if call_id:
                self.tools.resolve(call_id, msg)
        elif msg_type == "playback":
            d = asdict(msg) if hasattr(msg, "__dataclass_fields__") else msg
            self.metrics.on_playback(d)
        elif msg_type == "telemetry":
            self.telemetry = asdict(msg) if hasattr(msg, "__dataclass_fields__") else msg

    async def run(self) -> None:
        """Runs the session reader loop and supervises all pipeline stages."""
        stages = [
            ("ingest", lambda: ingest_stage(self)),
            ("stt", lambda: stt_stage(self)),
            ("llm", lambda: llm_stage(self)),
            ("tts", lambda: tts_stage(self)),
            ("egress", lambda: egress_stage(self)),
        ]
        self._tasks = [asyncio.create_task(supervise(name, factory, self), name=f"stage-{name}") for name, factory in stages]
        reader_task = asyncio.create_task(self.reader(), name="session-reader")

        try:
            # When the reader exits (WebSocket closed), stop all stages
            await reader_task
        finally:
            for t in self._tasks:
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def reader(self) -> None:
        """Inbound WebSocket message pump."""
        try:
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    self.on_audio(raw)
                else:
                    self.on_json(parse_message(raw))
        except Exception as e:
            log.info("Session %s connection ended: %s", self.id, e)

    async def close(self) -> None:
        """Closes the session and associated socket."""
        if self._closed:
            return
        self._closed = True
        if self.scope:
            self.scope.cancel()
        try:
            await self.ws.close()
        except Exception:
            pass
