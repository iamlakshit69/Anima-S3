"""
server/anima_server/audio/rechunk.py — Fixed-size audio block re-chunker.
"""

from __future__ import annotations

from typing import Iterator

import numpy as np


class Rechunker:
    """Collects variable-sized PCM chunks and yields blocks of exact length `block_size`."""

    def __init__(self, block_size: int):
        self.block_size = block_size
        self._buffer = np.zeros(0, dtype=np.int16)

    def push(self, pcm: np.ndarray) -> Iterator[np.ndarray]:
        """Pushes new PCM samples and yields any full blocks of size `block_size`."""
        if len(pcm) == 0:
            return

        if len(self._buffer) == 0:
            self._buffer = pcm.copy()
        else:
            self._buffer = np.concatenate((self._buffer, pcm))

        while len(self._buffer) >= self.block_size:
            block = self._buffer[: self.block_size]
            self._buffer = self._buffer[self.block_size :]
            yield block

    def flush(self) -> np.ndarray:
        """Flushes and returns remaining samples (may be shorter than block_size)."""
        rem = self._buffer
        self._buffer = np.zeros(0, dtype=np.int16)
        return rem

    def reset(self) -> None:
        """Clears any buffered samples."""
        self._buffer = np.zeros(0, dtype=np.int16)

