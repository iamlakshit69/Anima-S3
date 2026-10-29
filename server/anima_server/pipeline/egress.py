"""
server/anima_server/pipeline/egress.py — Downlink audio pacing and WebSocket transmission.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from anima_server.core.sentinel import END_OF_SPEECH
from anima_server.transport.protocol import ReplyMsg, TtsStart, TtsStop
from anima_server.transport.protocol_gen import (
    AudioFrame,
    FLAG_FIRST,
    FLAG_LAST,
    KIND_DOWN,
)

log = logging.getLogger("anima.pipeline.egress")


@dataclass
class AudioChunk:
    pcm: np.ndarray
    sample_rate: int
    text: str = ""


class Pacer:
    """Paces downlink Opus frames according to configured lead buffer and frame duration."""

    def __init__(self, lead_ms: int = 1000, frame_ms: int = 20):
        self.lead = lead_ms / 1000.0
        self.frame = frame_ms / 1000.0
        self.t0: float | None = None
        self.sent = 0

    async def wait(self) -> None:
        loop = asyncio.get_running_loop()
        now_t = loop.time()
        if self.t0 is None:
            self.t0 = now_t

        due = self.t0 + self.sent * self.frame - self.lead
        if due < now_t - 0.2:
            # Starved: restarted clock
            self.t0 = now_t
            self.sent = 0
            due = now_t - self.lead

        if due > now_t:
            await asyncio.sleep(due - now_t)
        self.sent += 1


async def send_frame(
    session: Any,
    turn: int,
    opus_bytes: bytes,
    seq: int,
    first: bool = False,
    last: bool = False,
    t_ms: int = 0,
) -> None:
    flags = 0
    if first:
        flags |= FLAG_FIRST
    if last:
        flags |= FLAG_LAST

    frame = AudioFrame(
        kind=KIND_DOWN,
        flags=flags,
        seq=seq & 0xFFFF,
        turn=turn,
        t_ms=t_ms,
        opus=opus_bytes,
    )
    await session.send_raw_bytes(frame.encode())


async def egress_stage(session: Any) -> None:
    """Consumes generated PCM chunks, paces them, encodes to Opus, and transmits downlink frames."""
    pacer: Pacer | None = None
    started = False
    seq = 0
    stream_t0: float | None = None

    while True:
        turn, item = await session.egress_q.get()

        # Staleness check before work (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("egress")
            pacer, started = None, False
            continue

        if item is END_OF_SPEECH:
            if started and session.encoder is not None:
                for fr in session.encoder.flush():
                    t_ms = int((time.time() - (stream_t0 or time.time())) * 1000)
                    await send_frame(session, turn, fr, seq, last=True, t_ms=t_ms)
                    seq += 1

                await session.send(TtsStop(turn=turn, reason="done"))
                session.state = "IDLE"

            pacer, started = None, False
            stream_t0 = None
            continue

        if not started:
            await session.send(TtsStart(turn=turn))
            session.state = "SPEAKING"
            started = True
            pacer = Pacer(session.cfg.pacer_lead_ms, session.cfg.frame_ms)
            if session.encoder is not None:
                session.encoder.reset()
            session.latency.mark_once("first_frame_at")
            session.latency.log_latency_line()
            stream_t0 = time.time()
            seq = 0

        # Subtitle text message for device display
        if item.text:
            await session.send(ReplyMsg(turn=turn, text=item.text))

        # Encode PCM into 20ms frames and send
        pcm = item.pcm
        if session.encoder is not None:
            for fr in session.encoder.push(pcm):
                if session.is_stale(turn):
                    session.metrics.inc_stale("egress")
                    break
                assert pacer is not None
                await pacer.wait()
                # Re-check staleness after await (Rule T5)
                if session.is_stale(turn):
                    session.metrics.inc_stale("egress")
                    break

                t_ms = int((time.time() - (stream_t0 or time.time())) * 1000)
                await send_frame(session, turn, fr, seq, first=(seq == 0), t_ms=t_ms)
                seq += 1
