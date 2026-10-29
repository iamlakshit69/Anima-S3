"""
server/anima_server/pipeline/tts.py — TTS token accumulator and speech synthesizer.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from anima_server.core.retry import generate_error_tone
from anima_server.core.sentinel import END_OF_RESPONSE, END_OF_SPEECH
from anima_server.pipeline.egress import AudioChunk

log = logging.getLogger("anima.pipeline.tts")


def strip_markdown(text: str) -> str:
    """Removes common markdown symbols (asterisks, hashtags, backticks) for TTS synthesis."""
    text = re.sub(r"[*_`#~]", "", text)
    return text.strip()


async def accumulator(session: Any) -> None:
    """Groups streaming LLM tokens into synthesizable phrases, releasing the first phrase early."""
    buf = ""
    first = True

    while True:
        turn, tok = await session.token_q.get()

        # Staleness check before work (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("accumulator")
            buf = ""
            first = True
            continue

        if tok is END_OF_RESPONSE:
            if buf.strip():
                await session.phrase_q.put((turn, buf.strip()))
            await session.phrase_q.put((turn, END_OF_RESPONSE))
            buf = ""
            first = True
            continue

        buf += str(tok)
        min_chars = session.cfg.first_phrase_min_chars if first else session.cfg.min_phrase_chars

        # Check for phrase boundary punctuation (.!?,:;) or maximum phrase length
        trimmed = buf.rstrip()
        has_punctuation = len(trimmed) > 0 and trimmed[-1] in ".!?,:;"
        if (len(buf) >= min_chars and has_punctuation) or len(buf) >= session.cfg.max_phrase_chars:
            await session.phrase_q.put((turn, buf.strip()))
            buf = ""
            first = False


async def synthesizer(session: Any) -> None:
    """Synthesizes text phrases into PCM audio using Kokoro TTS."""
    while True:
        turn, phrase = await session.phrase_q.get()

        # Staleness check before work (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("synthesizer")
            continue

        if phrase is END_OF_RESPONSE:
            await session.egress_q.put((turn, END_OF_SPEECH))
            continue

        clean_text = strip_markdown(phrase)
        if not clean_text:
            continue

        try:
            pcm, sr = await session.models.run_cpu(
                session.models.kokoro.create,
                clean_text,
                voice=session.cfg.voice,
                speed=session.cfg.speed,
                sem=session.models._kokoro_sem,
            )
        except Exception as e:
            log.warning("TTS synthesis failed for '%s': %s. Generating error tone.", clean_text, e)
            pcm, sr = generate_error_tone(session.cfg.down_rate), session.cfg.down_rate

        # Re-check staleness after await (Rule T5)
        if session.is_stale(turn):
            session.metrics.inc_stale("synthesizer")
            continue

        session.latency.mark_once("tts_first_phrase_at")
        await session.egress_q.put((turn, AudioChunk(pcm=pcm, sample_rate=sr, text=phrase)))


async def tts_stage(session: Any) -> None:
    """Supervised TTS stage wrapping accumulator and synthesizer."""
    await asyncio.gather(accumulator(session), synthesizer(session))
