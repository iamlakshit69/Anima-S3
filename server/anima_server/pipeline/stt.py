"""
server/anima_server/pipeline/stt.py — Speech-to-text stage with faster-whisper.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from anima_server.audio import dsp
from anima_server.transport.protocol import SttMsg

log = logging.getLogger("anima.pipeline.stt")


async def stt_stage(session: Any) -> None:
    """Supervised STT pipeline stage."""
    while True:
        turn, audio = await session.stt_q.get()

        # Staleness check before work (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("stt")
            continue

        audio = dsp.trim_trailing_silence(audio, rate=session.cfg.up_rate)
        dur = len(audio) / session.cfg.up_rate

        # Guard against too-short audio or silence
        if (dur * 1000.0 < session.cfg.min_audio_ms) or (dsp.rms(audio) < session.cfg.min_audio_rms):
            log.info("Audio in turn %d too short or quiet (%.2fs, rms=%.4f). Dropping.", turn, dur, dsp.rms(audio))
            session.finish_turn(turn, reason="empty")
            continue

        norm_audio = dsp.normalize(audio)

        try:
            # Run CPU inference via ModelHub threadpool
            if hasattr(session.models.whisper, "transcribe"):
                # faster_whisper returns (segments, info) or text
                res = await session.models.run_cpu(
                    session.models.whisper.transcribe,
                    norm_audio,
                    sem=session.models._whisper_sem,
                )
                if isinstance(res, tuple):
                    segments, _ = res
                    text = " ".join(seg.text for seg in segments).strip()
                else:
                    text = str(res).strip()
            else:
                text = ""
        except Exception as e:
            log.exception("STT transcription failed for turn %d: %s", turn, e)
            await session.send_error(code="E_STT_FAIL", text="Transcription error", fatal=False)
            session.finish_turn(turn, reason="error")
            continue

        # Re-check staleness after await (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("stt")
            continue

        session.latency.stt_done_at = time.time()
        log.info("STT turn %d transcript: '%s' (dur=%.2fs)", turn, text, dur)

        if not text or dsp.is_hallucination(text, dur):
            log.info("Filtered empty text or hallucination in turn %d: '%s'", turn, text)
            session.finish_turn(turn, reason="empty")
            continue

        # Emit SttMsg to device for subtitle display
        await session.send(SttMsg(turn=turn, text=text))
        await session.llm_q.put((turn, text))

