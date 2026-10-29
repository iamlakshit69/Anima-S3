#!/usr/bin/env python3
"""
tools/fake_device.py — Simulated ESP32 satellite for testing and drills (Architecture section 9.1).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, List, Optional

import numpy as np
import websockets

# Include server path to access protocol & codecs
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

from anima_server.audio.opus_codec import OpusDecoder, OpusEncoder
from anima_server.transport.protocol import (
    Hello,
    ListenStart,
    PlaybackMsg,
    ToolResultMsg,
    decode_frame,
    parse_message,
)
from anima_server.transport.protocol_gen import (
    AudioFrame,
    FLAG_FIRST,
    FLAG_LAST,
    KIND_UP,
    PROTO_VERSION,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [fake_dev] %(message)s")
log = logging.getLogger("fake_device")


def generate_synthetic_speech(rate: int = 16000, duration_s: float = 1.0) -> np.ndarray:
    """Generates synthetic voiced audio (fundamental + harmonics) for testing."""
    t = np.linspace(0, duration_s, int(rate * duration_s), endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 200.0 * t) + 0.3 * np.sin(2 * np.pi * 400.0 * t)
    return (sig * 32767).astype(np.int16)


class FakeDevice:
    def __init__(self, url: str, token: str, device_id: str = "esp32s3-fake-01"):
        self.url = url
        self.token = token
        self.device_id = device_id
        self.turn = 1
        self.encoder = OpusEncoder(rate=16000, channels=1, frame_ms=20, bitrate=20000)
        self.decoder = OpusDecoder(rate=24000, channels=1, frame_ms=20)
        self.received_messages: List[Any] = []
        self.received_audio_frames: List[AudioFrame] = []
        self.ws: Any = None
        self.ttfa: Optional[float] = None
        self._listen_stop_event = asyncio.Event()
        self._tts_start_time: Optional[float] = None
        self._endpoint_time: Optional[float] = None

    async def connect(self) -> None:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Device-Id": self.device_id,
        }
        log.info("Connecting to %s (device_id=%s)", self.url, self.device_id)
        # websockets v14+ uses additional_headers
        self.ws = await websockets.connect(self.url, additional_headers=headers)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()

    async def send_json(self, msg: Any) -> None:
        payload = asdict(msg) if hasattr(msg, "__dataclass_fields__") else msg
        await self.ws.send(json.dumps(payload))

    async def send_audio_frame(self, frame: AudioFrame) -> None:
        await self.ws.send(frame.encode())

    async def handshake(self) -> Any:
        tools = [
            {
                "name": "set_volume",
                "description": "Set speaker volume 0-100",
                "params": {
                    "type": "object",
                    "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
                    "required": ["level"],
                },
                "risk": "safe",
            }
        ]
        hello = Hello(
            proto=PROTO_VERSION,
            device_id=self.device_id,
            fw="1.0.0-fake",
            board="esp32s3-sim",
            features=["opus", "tools"],
            last_turn=self.turn - 1,
            tools=tools,
        )
        await self.send_json(hello)
        raw_ack = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
        ack = parse_message(raw_ack)
        log.info("Received handshake ack: %s", ack)
        return ack

    async def stream_pcm_uplink(self, pcm: np.ndarray, turn: int, drop_frames: int = 0, trailing_silence_s: float = 0.3) -> None:
        """Pushes PCM through Opus encoder and streams 20ms frames paced in real time."""
        if trailing_silence_s > 0:
            silence = np.zeros(int(16000 * trailing_silence_s), dtype=np.int16)
            pcm = np.concatenate((pcm, silence))

        seq = 0
        frames = list(self.encoder.push(pcm)) + list(self.encoder.flush())
        t0 = time.time()

        for idx, fr in enumerate(frames):
            if drop_frames > 0 and idx < drop_frames:
                log.info("Fault injection: dropping frame seq=%d", seq)
                seq += 1
                continue

            first = idx == 0
            last = idx == len(frames) - 1
            flags = (FLAG_FIRST if first else 0) | (FLAG_LAST if last else 0)
            t_ms = int((time.time() - t0) * 1000)

            frame = AudioFrame(
                kind=KIND_UP,
                flags=flags,
                seq=seq & 0xFFFF,
                turn=turn,
                t_ms=t_ms,
                opus=fr,
            )
            await self.send_audio_frame(frame)
            seq += 1
            await asyncio.sleep(0.02)  # Real-time 20ms pacing

    async def reader_loop(self) -> None:
        """Reads inbound messages from the server."""
        try:
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    f = decode_frame(raw)
                    if f:
                        # Rule T7: drop late turn audio
                        if f.turn < self.turn:
                            log.warning("Dropping late downlink frame (frame.turn=%d, current=%d)", f.turn, self.turn)
                            continue
                        if not self.received_audio_frames and self._endpoint_time:
                            self.ttfa = time.time() - self._endpoint_time
                            log.info("First downlink audio frame received! TTFA = %.3fs", self.ttfa)
                        self.received_audio_frames.append(f)
                else:
                    msg = parse_message(raw)
                    self.received_messages.append(msg)
                    msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)

                    if msg_type == "listen.stop":
                        self._endpoint_time = time.time()
                        self._listen_stop_event.set()
                        log.info("Received listen.stop (reason=%s)", getattr(msg, "reason", "unknown"))

                    elif msg_type == "tool.call":
                        call_id = getattr(msg, "id", "")
                        name = getattr(msg, "name", "")
                        log.info("Received tool.call: %s (id=%s). Executing fake tool...", name, call_id)
                        # Reply with tool.result
                        await self.send_json(
                            ToolResultMsg(
                                turn=self.turn,
                                id=call_id,
                                ok=True,
                                result={"status": "ok", "value": 40},
                            )
                        )

                    elif msg_type == "tts.stop":
                        log.info("Received tts.stop. Playback finished.")
                        await self.send_json(PlaybackMsg(turn=self.turn, event="finished"))
        except Exception as e:
            log.debug("Reader loop ended: %s", e)


async def run_scenario(args: argparse.Namespace) -> int:
    scenario = args.scenario
    log.info("=== Running Scenario: %s ===", scenario)

    dev = FakeDevice(url=args.url, token=args.token, device_id=args.device_id)

    if scenario == "bad_token":
        dev.token = "wrong-invalid-token"
        try:
            await dev.connect()
            log.error("Expected connection rejection with bad token, but connection succeeded")
            return 1
        except Exception as e:
            log.info("Bad token correctly rejected: %s", e)
            return 0

    await dev.connect()
    ack = await dev.handshake()
    reader_task = asyncio.create_task(dev.reader_loop())

    try:
        if scenario == "normal":
            dev.turn = 1
            await dev.send_json(ListenStart(turn=dev.turn, reason="wake_word"))
            pcm = generate_synthetic_speech(duration_s=1.2)
            await dev.stream_pcm_uplink(pcm, turn=dev.turn, drop_frames=args.drop_frames)
            # Wait for reply
            await asyncio.sleep(2.5)

        elif scenario == "no_speech":
            dev.turn = 1
            await dev.send_json(ListenStart(turn=dev.turn, reason="wake_word"))
            # Stream silence or nothing
            await asyncio.sleep(2.0)

        elif scenario == "tool_call":
            dev.turn = 1
            await dev.send_json(ListenStart(turn=dev.turn, reason="wake_word"))
            pcm = generate_synthetic_speech(duration_s=1.0)
            await dev.stream_pcm_uplink(pcm, turn=dev.turn)
            await asyncio.sleep(3.0)

        elif scenario == "barge_in":
            # Turn 1
            dev.turn = 1
            await dev.send_json(ListenStart(turn=dev.turn, reason="wake_word"))
            pcm = generate_synthetic_speech(duration_s=1.0)
            await dev.stream_pcm_uplink(pcm, turn=dev.turn)
            await asyncio.sleep(0.5)

            # Barge-in: flush turn 1, increment turn to 2
            log.info("Triggering barge-in tap! Incrementing turn to 2")
            await dev.send_json(PlaybackMsg(turn=dev.turn, event="flushed"))
            dev.turn = 2
            await dev.send_json(ListenStart(turn=dev.turn, reason="barge_in"))

            # Optionally send late stale frames if requested
            if args.late_frames_after_barge_in > 0:
                log.info("Injecting %d late turn 1 frames after barge-in", args.late_frames_after_barge_in)
                for _ in range(args.late_frames_after_barge_in):
                    stale_frame = AudioFrame(
                        kind=KIND_UP,
                        flags=0,
                        seq=999,
                        turn=1,
                        t_ms=5000,
                        opus=b"\x00" * 30,
                    )
                    await dev.send_audio_frame(stale_frame)

            pcm2 = generate_synthetic_speech(duration_s=0.8)
            await dev.stream_pcm_uplink(pcm2, turn=dev.turn)
            await asyncio.sleep(2.5)

        elif scenario == "reconnect":
            log.info("Simulating network disconnection...")
            await dev.close()
            reader_task.cancel()
            await asyncio.sleep(1.0)
            log.info("Reconnecting with fresh hello and last_turn=%d...", dev.turn)
            await dev.connect()
            await dev.handshake()
            reader_task = asyncio.create_task(dev.reader_loop())
            dev.turn += 1
            await dev.send_json(ListenStart(turn=dev.turn, reason="button"))
            pcm = generate_synthetic_speech(duration_s=0.8)
            await dev.stream_pcm_uplink(pcm, turn=dev.turn)
            await asyncio.sleep(2.0)

        log.info("Scenario %s completed. Received %d JSON msgs, %d audio frames", scenario, len(dev.received_messages), len(dev.received_audio_frames))
        return 0

    finally:
        reader_task.cancel()
        await dev.close()


def main():
    parser = argparse.ArgumentParser(description="ANIMA-S3 Simulated ESP32 Satellite")
    parser.add_argument("--url", default="ws://127.0.0.1:8765/v1/device", help="WebSocket URL")
    parser.add_argument("--token", default="test-token-32-chars-long-fake-dev", help="Bearer token")
    parser.add_argument("--device-id", default="esp32s3-fake-01", help="Device ID header")
    parser.add_argument("--wav", type=Path, help="Input WAV file to stream as user speech")
    parser.add_argument("--out", type=Path, help="Output WAV path to record server reply")
    parser.add_argument(
        "--scenario",
        default="normal",
        choices=["normal", "barge_in", "tool_call", "no_speech", "reconnect", "stale_audio", "bad_token"],
        help="Test scenario to execute",
    )
    parser.add_argument("--drop-frames", type=int, default=0, help="Simulate dropped uplink audio frames")
    parser.add_argument("--jitter-ms", type=int, default=0, help="Add network jitter to frame delivery (ms)")
    parser.add_argument("--late-frames-after-barge-in", type=int, default=0, help="Send stale frames after barge-in")
    args = parser.parse_args()

    sys.exit(asyncio.run(run_scenario(args)))


if __name__ == "__main__":
    main()
