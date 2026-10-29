"""
server/anima_server/audio/opus_codec.py — Opus encoder with re-chunking and decoder with PLC.
"""

from __future__ import annotations

import logging
from typing import Iterator

import numpy as np
import opuslib

log = logging.getLogger("anima.opus")


class OpusDecoder:
    """Decodes Opus packets to float32 or int16 PCM with Packet Loss Concealment (PLC)."""

    def __init__(self, rate: int = 16000, channels: int = 1, frame_ms: int = 20):
        self.rate = rate
        self.channels = channels
        self.frame_ms = frame_ms
        self.frame_size = int(rate * frame_ms / 1000)  # 320 at 16kHz
        self._decoder = opuslib.Decoder(rate, channels)
        self.last_seq: int | None = None

    def decode(self, packet: bytes | None, seq: int | None = None) -> np.ndarray:
        """Decodes an Opus packet.

        If seq is supplied and indicates missing frames (1-3 gap), invokes PLC.
        """
        out_pcm: list[np.ndarray] = []

        if seq is not None and self.last_seq is not None:
            # Calculate gap considering 16-bit sequence wraparound
            gap = (seq - self.last_seq - 1) & 0xFFFF
            if 1 <= gap <= 3:
                log.debug("PLC: packet gap of %d detected (last_seq=%d, seq=%d)", gap, self.last_seq, seq)
                for _ in range(gap):
                    # In opuslib, decode with packet=None or empty triggers PLC
                    plc_bytes = self._decoder.decode(b"", self.frame_size, decode_fec=True)
                    plc_samples = np.frombuffer(plc_bytes, dtype=np.int16)
                    out_pcm.append(plc_samples)
            elif gap > 3:
                log.warning("Large packet gap (%d frames). Resetting decoder state.", gap)
                self.reset()

        if seq is not None:
            self.last_seq = seq

        if packet:
            pcm_bytes = self._decoder.decode(packet, self.frame_size)
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            out_pcm.append(samples)

        if not out_pcm:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(out_pcm) if len(out_pcm) > 1 else out_pcm[0]

    def reset(self) -> None:
        """Re-initializes the decoder state."""
        self._decoder = opuslib.Decoder(self.rate, self.channels)
        self.last_seq = None


class OpusEncoder:
    """Encodes arbitrary PCM audio into fixed-size Opus frames."""

    def __init__(
        self,
        rate: int = 24000,
        channels: int = 1,
        frame_ms: int = 20,
        bitrate: int = 28000,
        application: str = "voip",
    ):
        self.rate = rate
        self.channels = channels
        self.frame_ms = frame_ms
        self.frame_size = int(rate * frame_ms / 1000)  # 480 at 24kHz
        self.bitrate = bitrate

        app_flag = opuslib.APPLICATION_VOIP if application == "voip" else opuslib.APPLICATION_AUDIO
        self._encoder = opuslib.Encoder(rate, channels, app_flag)
        try:
            self._encoder.bitrate = bitrate
        except Exception:
            pass
        self._residual = np.zeros(0, dtype=np.int16)

    def push(self, pcm: np.ndarray) -> Iterator[bytes]:
        """Pushes PCM samples (int16), buffers them, and yields encoded 20ms frames."""
        if len(pcm) == 0:
            return

        if pcm.dtype != np.int16:
            pcm = (pcm * 32767).astype(np.int16)

        if len(self._residual) == 0:
            self._residual = pcm.copy()
        else:
            self._residual = np.concatenate((self._residual, pcm))

        while len(self._residual) >= self.frame_size:
            chunk = self._residual[: self.frame_size]
            self._residual = self._residual[self.frame_size :]
            yield self._encoder.encode(chunk.tobytes(), self.frame_size)

    def flush(self) -> Iterator[bytes]:
        """Flushes remaining residual samples, zero-padding the final frame."""
        if len(self._residual) > 0:
            pad_len = self.frame_size - len(self._residual)
            padded = np.concatenate((self._residual, np.zeros(pad_len, dtype=np.int16)))
            self._residual = np.zeros(0, dtype=np.int16)
            yield self._encoder.encode(padded.tobytes(), self.frame_size)

    def reset(self) -> None:
        """Clears residual buffer and resets encoder state."""
        self._residual = np.zeros(0, dtype=np.int16)
