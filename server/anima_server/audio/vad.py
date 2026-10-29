"""
server/anima_server/audio/vad.py — Voice Activity Detection wrapper (ONNX + Energy fallback).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger("anima.vad")


class FakeVAD:
    """Deterministic VAD for testing."""

    def __init__(self, default_prob: float = 0.0):
        self.default_prob = default_prob
        self.scripted_probs: list[float] = []

    def set_script(self, probs: list[float]) -> None:
        self.scripted_probs = list(probs)

    def prob(self, pcm_512: np.ndarray) -> float:
        if self.scripted_probs:
            return self.scripted_probs.pop(0)
        return self.default_prob


class SileroVAD:
    """Silero VAD implementation using ONNX Runtime, with energy-based fallback."""

    def __init__(self, model_path: str | None = None):
        self.session = None
        if model_path:
            try:
                import onnxruntime as ort

                opts = ort.SessionOptions()
                opts.inter_op_num_threads = 1
                opts.intra_op_num_threads = 1
                self.session = ort.InferenceSession(model_path, sess_options=opts)
                self.reset()
                log.info("Loaded Silero VAD from %s", model_path)
            except Exception as e:
                log.warning("Could not initialize Silero ONNX VAD: %s. Using energy fallback.", e)

    def reset(self) -> None:
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def prob(self, pcm_512: np.ndarray) -> float:
        """Computes speech probability for a 512-sample (32ms at 16kHz) audio block."""
        if len(pcm_512) != 512:
            return 0.0

        if self.session is not None:
            try:
                audio_float = pcm_512.astype(np.float32) / 32768.0 if pcm_512.dtype == np.int16 else pcm_512
                audio_tensor = np.expand_dims(audio_float, axis=0)  # (1, 512)
                sr_tensor = np.array(16000, dtype=np.int64)

                inputs = {
                    "input": audio_tensor,
                    "sr": sr_tensor,
                    "h": self._h,
                    "c": self._c,
                }
                out, self._h, self._c = self.session.run(None, inputs)
                return float(out[0][0])
            except Exception as e:
                log.error("VAD inference error: %s", e)

        # Fallback: RMS energy-based pseudo probability
        float_audio = pcm_512.astype(np.float32) / 32768.0 if pcm_512.dtype == np.int16 else pcm_512
        rms = float(np.sqrt(np.mean(float_audio**2)))
        # Map rms 0.01 -> 0.0, 0.08+ -> 1.0
        return float(np.clip((rms - 0.01) / 0.07, 0.0, 1.0))
