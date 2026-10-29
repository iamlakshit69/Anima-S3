"""
server/anima_server/transport/ws_server.py — WebSocket connection handler, auth, and handshake.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

from anima_server.config import Config
from anima_server.transport.protocol import (
    ErrorMsg,
    Hello,
    HelloAck,
    parse_message,
)
from anima_server.transport.protocol_gen import (
    E_BUSY,
    E_PROTO_VERSION,
    PROTO_VERSION,
)
from anima_server.transport.session import Session

log = logging.getLogger("anima.transport.ws")

SERVER_VERSION = "0.1.0"


def authenticate_headers(headers: Any, cfg: Config) -> tuple[bool, str]:
    """Validates Authorization Bearer token and extracts X-Device-Id.

    Returns (is_authenticated, device_id).
    """
    if not cfg.device_tokens:
        # Development mode without tokens configured
        return True, "dev-device"

    auth_header = ""
    dev_id = "default"

    # headers can be a dict, list of tuples, or Headers object
    if hasattr(headers, "get"):
        auth_header = headers.get("Authorization", "")
        dev_id = headers.get("X-Device-Id", "default")
    elif isinstance(headers, (list, tuple)):
        for k, v in headers:
            if k.lower() == "authorization":
                auth_header = v
            elif k.lower() == "x-device-id":
                dev_id = v

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    expected_token = cfg.device_tokens.get(dev_id, cfg.device_tokens.get("default"))
    if not token or token != expected_token:
        log.warning("Authentication failed for device '%s' (token mismatch or missing)", dev_id)
        return False, dev_id

    return True, dev_id


class WsServer:
    def __init__(self, cfg: Config, models: Any, provider: Any):
        self.cfg = cfg
        self.models = models
        self.provider = provider
        self.active_sessions: Set[Session] = set()

    async def handle_connection(self, ws: Any) -> None:
        """Handles an incoming WebSocket satellite connection."""
        req = getattr(ws, "request", None)
        headers = getattr(req, "headers", getattr(ws, "headers", {}))
        ok, dev_id = authenticate_headers(headers, self.cfg)
        if not ok:
            # 4401: Unauthorized application close code
            await ws.close(code=4401, reason="Unauthorized")
            return

        # 1. Wait for hello message within hello_timeout_s
        try:
            raw_hello = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = parse_message(raw_hello)
            if not isinstance(msg, Hello) and (not isinstance(msg, dict) or msg.get("type") != "hello"):
                log.warning("First message from %s was not hello. Closing.", dev_id)
                await ws.close(code=4400, reason="Expected hello")
                return
            if isinstance(msg, dict):
                msg = Hello(**{k: v for k, v in msg.items() if k in Hello.__dataclass_fields__})
        except asyncio.TimeoutError:
            log.warning("Device %s timed out waiting for hello handshake", dev_id)
            await ws.close(code=4408, reason="Hello timeout")
            return

        # 2. Check protocol version
        if msg.proto != PROTO_VERSION:
            err = ErrorMsg(code=E_PROTO_VERSION, text=f"Unsupported protocol version {msg.proto}", fatal=True)
            await ws.send(json.dumps(err.__dict__))
            await ws.close(code=4402, reason="Protocol version mismatch")
            return

        # 3. Check capacity limit
        if len(self.active_sessions) >= self.cfg.max_sessions:
            err = ErrorMsg(code=E_BUSY, text="Server at session capacity", fatal=True)
            await ws.send(json.dumps(err.__dict__))
            await ws.close(code=4429, reason="Server busy")
            return

        # 4. Construct and register session
        session = Session(
            device_id=dev_id,
            ws=ws,
            cfg=self.cfg,
            models=self.models,
            provider=self.provider,
            hello=msg,
        )
        self.active_sessions.add(session)
        log.info("Session %s registered for device %s (active: %d)", session.id, dev_id, len(self.active_sessions))

        # 5. Send hello_ack
        ack = HelloAck(
            proto=PROTO_VERSION,
            session_id=session.id,
            server=SERVER_VERSION,
            listen_timeout_ms=self.cfg.listen_timeout_ms,
            max_turn_ms=self.cfg.max_turn_ms,
        )
        await session.send(ack)

        try:
            await session.run()
        finally:
            self.active_sessions.discard(session)
            await session.close()
            log.info("Session %s deregistered for device %s (remaining: %d)", session.id, dev_id, len(self.active_sessions))
