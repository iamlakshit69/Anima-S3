"""
server/anima_server/main.py — Main server entry point.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

import websockets

from anima_server.admin.api import start_admin_api
from anima_server.config import Config, load_config, validate
from anima_server.core.logger import setup_logging
from anima_server.models import ModelHub
from anima_server.providers.openai_compat import OpenAICompatProvider
from anima_server.transport.ws_server import WsServer

log = logging.getLogger("anima.main")


async def run_server(cfg: Config, use_fakes: bool = False) -> None:
    """Initializes models, provider, and runs WebSocket server."""
    setup_logging()
    validate(cfg)
    log.info("Starting ANIMA-S3 Server on %s:%d (provider=%s, model=%s)", cfg.host, cfg.port, cfg.llm_provider, cfg.llm_model)

    # 1. Load models
    models = await ModelHub.load(cfg, use_fakes=use_fakes)

    # 2. Initialize and validate LLM provider
    if use_fakes:
        from anima_server.providers.base import Done, TextDelta

        class FakeProvider:
            async def validate(self):
                pass

            async def stream(self, messages, tools, scope):
                yield TextDelta("Hello! I am ANIMA.")
                yield Done(reason="stop")

        provider = FakeProvider()
    else:
        provider = OpenAICompatProvider(cfg)
        if cfg.llm_api_key:
            await provider.validate()
        else:
            log.warning("No LLM API key provided; skipping provider.validate() on startup")

    ws_server = WsServer(cfg, models, provider)

    # 3. SSL Context setup if configured (Decision 001)
    ssl_context = None
    if cfg.ssl_certfile and cfg.ssl_keyfile:
        import ssl

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(cfg.ssl_certfile, keyfile=cfg.ssl_keyfile)
        log.info("TLS enabled with certfile=%s", cfg.ssl_certfile)

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    # 4. Start Admin API (Architecture Section 6.11)
    admin_runner = await start_admin_api(cfg, ws_server)

    try:
        async with websockets.serve(
            ws_server.handle_connection,
            cfg.host,
            cfg.port,
            ssl=ssl_context,
            max_size=65536,
            ping_interval=10,
            ping_timeout=30,
        ):
            log.info("Server is listening on %s://%s:%d/v1/device", "wss" if ssl_context else "ws", cfg.host, cfg.port)
            await stop_event.wait()
            log.info("Server shutdown initiated")
    finally:
        await admin_runner.cleanup()


def main() -> None:
    import os
    cfg = load_config(".env")
    use_fakes = "--fakes" in sys.argv or os.getenv("USE_FAKES", "0").lower() in ("1", "true", "yes")
    try:
        asyncio.run(run_server(cfg, use_fakes=use_fakes))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

