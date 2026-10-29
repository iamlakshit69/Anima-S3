"""
Tests for Downlink frame Pacer (Architecture section 6.8).
"""

import asyncio
import time
import pytest
from anima_server.pipeline.egress import Pacer


@pytest.mark.asyncio
async def test_pacer_burst_up_to_lead():
    # 100ms lead, 20ms frames -> 5 frames can burst without sleep
    pacer = Pacer(lead_ms=100, frame_ms=20)

    t0 = time.time()
    for _ in range(5):
        await pacer.wait()
    elapsed = time.time() - t0

    # 5 frames within lead should complete immediately (< 50ms)
    assert elapsed < 0.05
    assert pacer.sent == 5


@pytest.mark.asyncio
async def test_pacer_paces_after_lead():
    # 40ms lead, 20ms frames -> after 2 frames, each subsequent frame sleeps ~20ms
    pacer = Pacer(lead_ms=40, frame_ms=20)

    t0 = time.time()
    for _ in range(5):
        await pacer.wait()
    elapsed = time.time() - t0

    # 5 frames: 2 burst (0ms), 3 paced (3 * 20ms = 60ms) -> allow scheduler jitter
    assert elapsed >= 0.035
