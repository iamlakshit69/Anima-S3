"""
server/anima_server/models.py — ModelHub for Whisper, Kokoro, and Silero models.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import numpy as np

from anima_server.audio.vad import FakeVAD, SileroVAD
from anima_server.config import Config

log = logging.getLogger("anima.models")


class FakeWhisper:
    def __init__(self, scripted_text: str = "Hello world"):
        self.scripted_text = scripted_text

    def transcribe(self, audio: np.ndarray) -> str:
        return self.scripted_text


class FakeKokoro:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def create(self, text: str, voice: str = "af_bella", speed: float = 1.0) -> tuple[np.ndarray, int]:
        # Generates a brief sine wave whose duration is proportional to text length
        dur = max(0.2, min(len(text) * 0.05, 2.0))
        num_samples = int(self.sample_rate * dur)
        t = np.linspace(0, dur, num_samples, endpoint=False)
        pcm = (np.sin(2 * np.pi * 440.0 * t) * 0.2 * 32767).astype(np.int16)
        return pcm, self.sample_rate


class ModelHub:
    """Central model container with warm-up and CPU execution controls."""

    def __init__(self, cfg: Config, whisper: Any, kokoro: Any, vad: Any):
        self.cfg = cfg
        self.whisper = whisper
        self.kokoro = kokoro
        self.vad = vad
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="model_worker")
        self._whisper_sem = asyncio.Semaphore(1)
        self._kokoro_sem = asyncio.Semaphore(1)

    @classmethod
    async def load(cls, cfg: Config, use_fakes: bool = False) -> ModelHub:
        """Loads models, initializes weights, and runs a warm-up inference."""
        if use_fakes:
            whisper = FakeWhisper()
            kokoro = FakeKokoro()
            vad = SileroVAD()
            log.info("Initialized ModelHub with deterministic test fakes")
            return cls(cfg, whisper, kokoro, vad)

        # 1. VAD
        vad = SileroVAD()

        # 2. Whisper
        try:
            from faster_whisper import WhisperModel

            log.info("Loading Whisper model: %s (compute=%s, device=%s)", cfg.whisper_model, cfg.whisper_compute, cfg.whisper_device)
            whisper = WhisperModel(
                cfg.whisper_model,
                device=cfg.whisper_device,
                compute_type=cfg.whisper_compute,
                cpu_threads=4,
                num_workers=1,
            )
        except Exception as e:
            log.warning("faster-whisper not available: %s. Using FakeWhisper.", e)
            whisper = FakeWhisper()

        # 3. Kokoro TTS
        try:
            from kokoro_onnx import Kokoro

            log.info("Loading Kokoro TTS model...")
            kokoro = Kokoro(cfg.kokoro_model, cfg.kokoro_voices)
        except Exception as e:
            log.warning("kokoro-onnx not available: %s. Using FakeKokoro.", e)
            kokoro = FakeKokoro()

        return cls(cfg, whisper, kokoro, vad)

    async def run_cpu(self, fn: Callable[..., Any], *args: Any, sem: asyncio.Semaphore | None = None, **kwargs: Any) -> Any:
        """Runs a CPU-bound function in the dedicated thread pool guarded by an optional semaphore."""
        loop = asyncio.get_running_loop()
        if sem:
            async with sem:
                return await loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))
        return await loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))
