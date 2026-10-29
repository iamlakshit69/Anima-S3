#!/usr/bin/env python3
"""
tools/fake_device.py — Simulated ESP32-S3 satellite for server testing and drills.

Implements the client side of the ANIMA-S3 wire protocol v1 (Architecture Section 9.1).
Scenarios:
  - normal: standard utterance, wait for reply audio, verify playback
  - barge_in: user interrupts assistant speech with a button tap
  - tool_call: server issues a device tool call, device executes allowlisted tool
  - no_speech: server times out waiting for speech
  - reconnect: simulated network drop and automatic backoff reconnection
  - stale_audio: sends stale turn frames to test server turn isolation
  - bad_token: handshake with invalid bearer token to test E_AUTH rejection
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add repo root to path so we can import protocol_gen
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

try:
    from anima_server.transport import protocol_gen as proto
except ImportError:
    proto = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fake_device")


def build_parser() -> argparse.ArgumentParser:
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
    # Fault injection flags
    parser.add_argument("--drop-frames", type=int, default=0, help="Simulate dropped uplink audio frames")
    parser.add_argument("--jitter-ms", type=int, default=0, help="Add network jitter to frame delivery (ms)")
    parser.add_argument("--disconnect-at", type=float, default=0.0, help="Simulate socket disconnect at T seconds")
    parser.add_argument("--late-frames-after-barge-in", type=int, default=0, help="Send stale frames after barge-in")
    return parser


async def run_scenario(args: argparse.Namespace) -> int:
    log.info("Starting fake_device scenario='%s' targeting '%s'", args.scenario, args.url)
    if proto is None:
        log.error("protocol_gen module not found. Run 'python protocol/gen.py' first.")
        return 1

    log.info("Protocol Version: %d, Header Size: %d", proto.PROTO_VERSION, proto.HEADER_SIZE)
    # Full scenario runner logic implemented in Phase 1
    log.info("fake_device initialized successfully. (Phase 0 skeleton ready)")
    return 0


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(run_scenario(args)))
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
