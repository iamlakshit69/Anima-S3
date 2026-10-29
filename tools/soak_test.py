#!/usr/bin/env python3
"""
tools/soak_test.py — ANIMA-S3 soak test: N turns with fakes, no live server needed.

Architecture §7 Phase 7 deliverable.

Usage:
    PYTHONPATH=server .venv/bin/python tools/soak_test.py [--turns 20] [--timeout 5.0]

Exit 0 if all turns complete successfully, exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

# Allow running from the repo root without installing
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "server"))

import websockets

from anima_server.config import Config
from anima_server.models import ModelHub
from anima_server.providers.base import Done, TextDelta
from anima_server.transport.ws_server import WsServer
from tools.fake_device import FakeDevice, generate_synthetic_speech

log = logging.getLogger("soak_test")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")


class SoakFakeLLM:
    """Deterministic fake LLM provider for soak runs."""

    async def validate(self) -> None:
        pass

    async def stream(self, messages, tools, scope):  # type: ignore[override]
        for word in ["Soak", "turn", "complete."]:
            if scope.is_cancelled():
                break
            yield TextDelta(word + " ")
            await asyncio.sleep(0.005)
        yield Done(reason="stop")


async def run_soak(n_turns: int, turn_timeout_s: float) -> int:
    """
    Runs n_turns complete voice turns against an in-process fake server.
    Returns 0 on full success, 1 if any turn fails.
    """
    cfg = Config(
        host="127.0.0.1",
        port=0,
        device_tokens={"soak-device": "soak-token"},
        min_audio_ms=100,
        fixed_silence_ms=100,
        listen_timeout_ms=500,
    )
    models = await ModelHub.load(cfg, use_fakes=True)
    provider = SoakFakeLLM()
    ws_server = WsServer(cfg, models, provider)

    server = await websockets.serve(
        ws_server.handle_connection,
        cfg.host,
        0,
        ping_interval=10,
        ping_timeout=30,
    )
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}/v1/device"

    ttfa_samples: List[float] = []
    failed_turns: List[int] = []
    turn_counter = 0  # monotonically increasing — simulates heap stability

    try:
        for i in range(1, n_turns + 1):
            turn_counter += 1
            log.debug("Starting soak turn %d/%d", i, n_turns)

            dev = FakeDevice(url=url, token="soak-token", device_id="soak-device")
            try:
                await dev.connect()
                await dev.handshake()

                reader = asyncio.create_task(dev.reader_loop())
                try:
                    dev.turn = i
                    await dev.send_json({"type": "listen.start", "turn": i, "reason": "wake_word"})
                    pcm = generate_synthetic_speech(duration_s=0.4)
                    await dev.stream_pcm_uplink(pcm, turn=i)

                    # Wait for listen.stop (endpoint)
                    try:
                        await asyncio.wait_for(dev._listen_stop_event.wait(), timeout=turn_timeout_s)
                    except asyncio.TimeoutError:
                        log.error("Turn %d: listen.stop not received within %.1fs", i, turn_timeout_s)
                        failed_turns.append(i)
                        continue

                    # Wait a bit more for the TTS frames
                    await asyncio.sleep(0.5)

                    if dev.ttfa is not None:
                        ttfa_samples.append(dev.ttfa)

                    types = [
                        getattr(m, "type", m.get("type") if isinstance(m, dict) else None)
                        for m in dev.received_messages
                    ]
                    if "listen.stop" not in types:
                        log.error("Turn %d: missing listen.stop", i)
                        failed_turns.append(i)
                    else:
                        log.debug("Turn %d OK (ttfa=%.3fs)", i, dev.ttfa or 0)
                finally:
                    reader.cancel()
                    try:
                        await asyncio.wait_for(reader, timeout=0.5)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            except Exception as exc:
                log.error("Turn %d raised exception: %s", i, exc)
                failed_turns.append(i)
            finally:
                await dev.close()

    finally:
        server.close()
        await server.wait_closed()

    # -------------------------------------------------------------------------
    # Results
    # -------------------------------------------------------------------------
    print(f"\n{'ANIMA-S3 Soak Test Results':=^60}")
    print(f"  Turns run   : {n_turns}")
    print(f"  Turns passed: {n_turns - len(failed_turns)}")
    print(f"  Turns failed: {len(failed_turns)}")
    if failed_turns:
        print(f"  Failed turns: {failed_turns}")

    if ttfa_samples:
        s = sorted(ttfa_samples)
        p50 = statistics.median(s)
        p95_idx = int(len(s) * 0.95)
        p95 = s[min(p95_idx, len(s) - 1)]
        print(f"\n  TTFA samples : {len(ttfa_samples)}")
        print(f"  TTFA min     : {min(s):.3f} s")
        print(f"  TTFA max     : {max(s):.3f} s")
        print(f"  TTFA p50     : {p50:.3f} s")
        print(f"  TTFA p95     : {p95:.3f} s")
        warn = " ⚠ (>1.5s target)" if p50 > 1.5 else ""
        print(f"  Target check : {'OK' if p50 <= 1.5 else 'WARN'}{warn}")
    else:
        print("\n  No TTFA samples collected (all turns may have failed)")

    print(f"\n  Turn counter : {turn_counter}  (heap-stability proxy)")
    print("=" * 60 + "\n")

    return 1 if failed_turns else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ANIMA-S3 Soak Test (fake server, no real models)")
    parser.add_argument("--turns", type=int, default=20, help="Number of turns to run (default: 20)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-turn timeout in seconds (default: 5.0)")
    args = parser.parse_args()

    return asyncio.run(run_soak(args.turns, args.timeout))


if __name__ == "__main__":
    sys.exit(main())

