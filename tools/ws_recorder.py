#!/usr/bin/env python3
"""
tools/ws_recorder.py — Records a WebSocket session to disk for deterministic replay.

Saves inbound/outbound binary audio frames and JSON control messages with microsecond timestamps.
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ws_recorder")


def main():
    parser = argparse.ArgumentParser(description="Record ANIMA WebSocket session")
    parser.add_argument("--url", default="ws://127.0.0.1:8765/v1/device", help="WebSocket endpoint")
    parser.add_argument("--out", required=True, help="Output session recording file (.jsonl / .bin)")
    args = parser.parse_args()
    log.info("ws_recorder initialized for endpoint %s -> output %s (Phase 0 skeleton)", args.url, args.out)


if __name__ == "__main__":
    main()

