"""
server/anima_server/audio/endpointer.py — Voice activity & utterance endpointer state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Protocol

import numpy as np

from anima_server.audio.rechunk import Rechunker
from anima_server.config import Config


class EndOfTurnPolicy(Protocol):
    def decide(self, silence_ms: int, speech_ms: int, partial_text: str | None = None) -> Literal["END", "WAIT"]:
        ...


class FixedPolicy:
    """Fixed silence duration endpoint policy (v1 default)."""

    def __init__(self, fixed_silence_ms: int = 700):
        self.fixed_silence_ms = fixed_silence_ms

    def decide(self, silence_ms: int, speech_ms: int, partial_text: str | None = None) -> Literal["END", "WAIT"]:
        return "END" if silence_ms >= self.fixed_silence_ms else "WAIT"


class VADModel(Protocol):
    def prob(self, pcm_512: np.ndarray) -> float:
        ...


@dataclass
class EndpointResult:
    reason: Literal["endpoint", "no_speech", "max_len"]
    audio: np.ndarray | None = None


# State definitions
STATE_WAITING = 0
STATE_IN_SPEECH = 1


class Endpointer:
    BLOCK_SAMPLES = 512  # 32ms at 16kHz
    BLOCK_MS = 32

    def __init__(self, cfg: Config, vad: VADModel, policy: EndOfTurnPolicy):
        self.cfg = cfg
        self.vad = vad
        self.policy = policy
        self.state = STATE_WAITING
        self.blocks: List[np.ndarray] = []
        self.total_ms = 0
        self.speech_ms = 0
        self.silence_ms = 0
        self.rechunk = Rechunker(self.BLOCK_SAMPLES)

    def feed(self, pcm: np.ndarray) -> EndpointResult | None:
        """Feeds PCM samples (16kHz int16 or float32) into the endpointer."""
        if len(pcm) == 0:
            return None

        # Ensure int16
        if pcm.dtype != np.int16:
            pcm = (pcm * 32767).astype(np.int16)

        for block in self.rechunk.push(pcm):
            prob = self.vad.prob(block)
            thr = self.cfg.vad_continue if self.state == STATE_IN_SPEECH else self.cfg.vad_onset
            is_speech = prob > thr

            self.blocks.append(block)
            self.total_ms += self.BLOCK_MS

            if self.state == STATE_WAITING:
                self.speech_ms = (self.speech_ms + self.BLOCK_MS) if is_speech else 0
                if self.speech_ms >= self.cfg.min_speech_ms:
                    self.state = STATE_IN_SPEECH
                    self.silence_ms = 0
                elif self.total_ms >= self.cfg.listen_timeout_ms:
                    return EndpointResult(reason="no_speech")
            else:
                self.silence_ms = 0 if is_speech else (self.silence_ms + self.BLOCK_MS)
                if self.policy.decide(self.silence_ms, self.speech_ms, None) == "END":
                    audio = np.concatenate(self.blocks) if self.blocks else np.zeros(0, dtype=np.int16)
                    return EndpointResult(reason="endpoint", audio=audio)
                if self.total_ms >= self.cfg.max_turn_ms:
                    audio = np.concatenate(self.blocks) if self.blocks else np.zeros(0, dtype=np.int16)
                    return EndpointResult(reason="max_len", audio=audio)

        return None

    def force_end(self) -> EndpointResult:
        """Forces turn end (e.g., on push-to-talk button release)."""
        rem = self.rechunk.flush()
        if len(rem) > 0:
            self.blocks.append(rem)
        audio = np.concatenate(self.blocks) if self.blocks else np.zeros(0, dtype=np.int16)
        return EndpointResult(reason="endpoint", audio=audio)

