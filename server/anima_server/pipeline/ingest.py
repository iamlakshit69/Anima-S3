"""
server/anima_server/pipeline/ingest.py — Uplink Opus audio decode and VAD endpointing stage.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from anima_server.transport.protocol import ListenStop

log = logging.getLogger("anima.pipeline.ingest")


async def ingest_stage(session: Any) -> None:
    """Supervised audio ingest pipeline stage."""
    while True:
        turn, frame = await session.ingest_q.get()

        # Staleness check before work (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("ingest")
            continue

        # Decode Opus frame (with packet loss concealment if seq gap)
        if session.decoder is not None:
            pcm = session.decoder.decode(frame.opus, seq=frame.seq)
        else:
            pcm = frame.opus

        if session.endpointer is None:
            continue

        res = session.endpointer.feed(pcm, partial_text=getattr(session, "partial_stt_text", None))
        if res is None:
            continue

        # Endpoint reached!
        session.state = "PROCESSING"
        session.latency.endpoint_at = time.time()
        log.info("Endpoint reached for turn %d (reason='%s')", turn, res.reason)

        await session.send(ListenStop(turn=turn, reason=res.reason))

        if res.reason == "no_speech":
            session.finish_turn(turn, reason="no_speech")
            continue

        if res.audio is not None:
            await session.stt_q.put((turn, res.audio))
