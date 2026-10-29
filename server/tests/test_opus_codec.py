"""
Tests for Opus codec with re-chunking and Packet Loss Concealment (PLC).
"""

import numpy as np
import pytest
from anima_server.audio.opus_codec import OpusDecoder, OpusEncoder


def test_encoder_rechunking_and_flush():
    encoder = OpusEncoder(rate=24000, channels=1, frame_ms=20)
    assert encoder.frame_size == 480

    # Push 1000 samples (should yield 2 frames of 480 = 960, leaving 40 in residual)
    samples = (np.sin(np.linspace(0, 1, 1000)) * 10000).astype(np.int16)
    frames = list(encoder.push(samples))
    assert len(frames) == 2
    for fr in frames:
        assert len(fr) > 0

    assert len(encoder._residual) == 40

    # Flush should pad remaining 40 to 480 and yield 1 final frame
    flushed = list(encoder.flush())
    assert len(flushed) == 1
    assert len(encoder._residual) == 0


def test_encode_decode_roundtrip():
    encoder = OpusEncoder(rate=16000, channels=1, frame_ms=20)
    decoder = OpusDecoder(rate=16000, channels=1, frame_ms=20)

    # 320 samples of 400Hz sine wave
    t = np.linspace(0, 0.02, 320, endpoint=False)
    orig_pcm = (np.sin(2 * np.pi * 400.0 * t) * 15000).astype(np.int16)

    frames = list(encoder.push(orig_pcm))
    assert len(frames) == 1

    dec_pcm = decoder.decode(frames[0], seq=0)
    assert len(dec_pcm) == 320
    assert dec_pcm.dtype == np.int16


def test_opus_plc_on_packet_gap():
    encoder = OpusEncoder(rate=16000, channels=1, frame_ms=20)
    decoder = OpusDecoder(rate=16000, channels=1, frame_ms=20)

    # Encode 3 frames
    t = np.linspace(0, 0.06, 960, endpoint=False)
    pcm = (np.sin(2 * np.pi * 400.0 * t) * 15000).astype(np.int16)
    frames = list(encoder.push(pcm))
    assert len(frames) == 3

    # Receive frame seq=0
    out0 = decoder.decode(frames[0], seq=0)
    assert len(out0) == 320

    # Skip frame seq=1, receive frame seq=2 -> gap of 1 frame -> PLC triggers for missing frame
    out2 = decoder.decode(frames[2], seq=2)
    # Total samples should be 320 (concealed) + 320 (frame 2) = 640
    assert len(out2) == 640
