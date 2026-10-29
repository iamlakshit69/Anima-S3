"""
server/anima_server/core/metrics.py — Latency measurements and operational counters.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("anima.metrics")


@dataclass
class TurnLatency:
    turn: int
    session_id: str = ""
    listen_start: float = field(default_factory=time.time)
    endpoint_at: float | None = None
    stt_done_at: float | None = None
    llm_first_token_at: float | None = None
    tts_first_phrase_at: float | None = None
    first_frame_at: float | None = None
    _logged: bool = False

    def mark_once(self, attr_name: str) -> None:
        if getattr(self, attr_name, None) is None:
            setattr(self, attr_name, time.time())

    def log_latency_line(self) -> str | None:
        """Emits the standard latency line per Architecture section 6.12."""
        if self._logged or self.endpoint_at is None or self.first_frame_at is None:
            return None
        self._logged = True

        endpoint_s = self.endpoint_at - self.listen_start
        stt_s = (self.stt_done_at - self.endpoint_at) if self.stt_done_at else 0.0
        llm_ttft_s = (
            (self.llm_first_token_at - self.stt_done_at)
            if (self.llm_first_token_at and self.stt_done_at)
            else 0.0
        )
        tts_s = (
            (self.tts_first_phrase_at - self.llm_first_token_at)
            if (self.tts_first_phrase_at and self.llm_first_token_at)
            else 0.0
        )
        ttfa_s = self.first_frame_at - self.endpoint_at

        line = (
            f"[latency] session={self.session_id} turn={self.turn} "
            f"endpoint={endpoint_s:.3f}s stt={stt_s:.3f}s llm_ttft={llm_ttft_s:.3f}s "
            f"tts={tts_s:.3f}s ttfa={ttfa_s:.3f}s"
        )
        log.info(line)
        return line


@dataclass
class SessionMetrics:
    bad_frames: int = 0
    dropped_frames: int = 0
    stale_listen_start: int = 0
    stale_items_dropped: dict[str, int] = field(default_factory=dict)
    underruns: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    reconnects: int = 0

    def inc_stale(self, stage: str) -> None:
        self.stale_items_dropped[stage] = self.stale_items_dropped.get(stage, 0) + 1

    def on_playback(self, msg: dict) -> None:
        event = msg.get("event")
        if event == "underrun":
            self.underruns += 1
            log.warning("Playback underrun reported by device in turn %s", msg.get("turn"))

