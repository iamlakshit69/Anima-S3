"""
server/anima_server/audio/dsp.py — Digital signal processing utilities and Whisper filtering.
"""

from __future__ import annotations

import re
import numpy as np

# Common Whisper hallucinations on brief ambient noise or silence
HALLUCINATION_PATTERNS = [
    re.compile(r"^\s*thank you\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*thanks for watching\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*bye\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*you\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*subtitles by\s*", re.IGNORECASE),
    re.compile(r"^\s*transcribed by\s*", re.IGNORECASE),
]


def rms(audio: np.ndarray) -> float:
    """Calculates RMS level for normalized float or int16 audio."""
    if len(audio) == 0:
        return 0.0
    if audio.dtype == np.int16:
        float_pcm = audio.astype(np.float32) / 32768.0
    else:
        float_pcm = audio.astype(np.float32)
    return float(np.sqrt(np.mean(float_pcm**2)))


def normalize(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Normalizes float32 audio to target peak amplitude."""
    if len(audio) == 0:
        return audio
    if audio.dtype == np.int16:
        pcm = audio.astype(np.float32) / 32768.0
    else:
        pcm = audio.copy().astype(np.float32)

    peak = np.max(np.abs(pcm))
    if peak > 1e-4:
        pcm = pcm * (target_peak / peak)
    return np.clip(pcm, -1.0, 1.0)


def trim_trailing_silence(audio: np.ndarray, rate: int = 16000, keep_ms: int = 320, threshold: float = 0.02) -> np.ndarray:
    """Trims silence from the end of an audio segment, keeping `keep_ms` trailing buffer."""
    if len(audio) == 0:
        return audio
    float_audio = audio.astype(np.float32) / 32768.0 if audio.dtype == np.int16 else audio

    chunk_size = int(rate * 0.02)  # 20ms
    if len(float_audio) <= chunk_size:
        return audio

    last_voiced_idx = len(float_audio)
    for i in range(len(float_audio) - chunk_size, 0, -chunk_size):
        chunk = float_audio[i : i + chunk_size]
        if np.sqrt(np.mean(chunk**2)) > threshold:
            last_voiced_idx = min(len(float_audio), i + chunk_size + int(rate * keep_ms / 1000.0))
            break

    return audio[:last_voiced_idx]


def is_hallucination(text: str, duration_s: float) -> bool:
    """Checks if a transcription is likely a Whisper hallucination."""
    t = text.strip()
    if not t:
        return True
    # For very short audio (<1.2s), check against known hallucination phrases
    if duration_s < 1.5:
        for pat in HALLUCINATION_PATTERNS:
            if pat.search(t):
                return True
    return False
