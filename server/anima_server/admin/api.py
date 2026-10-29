"""
server/anima_server/admin/api.py — Authenticated Admin & OTA Manifest API.

Architecture Section 6.11 and Rule R11:
- Runs on separate port/host from device WebSocket.
- Authenticated with dedicated bearer token.
- Only authority for firmware OTA manifests.
- Exposes /healthz, /metrics, /ota/manifest.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from aiohttp import web

from anima_server.config import Config

log = logging.getLogger("anima.admin.api")


class AdminAPI:
    def __init__(self, cfg: Config, ws_server: Any = None):
        self.cfg = cfg
        self.ws_server = ws_server
        self.start_time = time.time()
        self.app = web.Application(middlewares=[self._auth_middleware])
        self._setup_routes()

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler: Any) -> web.Response:
        """Enforces Bearer token authentication on all Admin API endpoints."""
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {self.cfg.admin_token}"

        if not auth_header or auth_header != expected:
            log.warning("Unauthorized access attempt to %s from %s", request.path, request.remote)
            return web.json_response({"error": "Unauthorized", "code": "E_AUTH"}, status=401)

        return await handler(request)

    def _setup_routes(self) -> None:
        self.app.router.add_get("/healthz", self.handle_healthz)
        self.app.router.add_get("/metrics", self.handle_metrics)
        self.app.router.add_get("/ota/manifest", self.handle_ota_manifest)

    async def handle_healthz(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        uptime = round(time.time() - self.start_time, 2)
        active_count = len(self.ws_server.sessions) if (self.ws_server and hasattr(self.ws_server, "sessions")) else 0
        return web.json_response({
            "status": "ok",
            "uptime_s": uptime,
            "active_sessions": active_count,
        })

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Metrics endpoint."""
        data = {
            "uptime_s": round(time.time() - self.start_time, 2),
            "sessions_total": getattr(self.ws_server, "total_sessions", 0) if self.ws_server else 0,
            "active_sessions": len(self.ws_server.sessions) if (self.ws_server and hasattr(self.ws_server, "sessions")) else 0,
        }
        return web.json_response(data)

    async def handle_ota_manifest(self, request: web.Request) -> web.Response:
        """Rule R11: OTA manifests are provided only via the authenticated Admin API."""
        device_id = request.query.get("device_id", "default")
        log.info("OTA manifest requested for device '%s'", device_id)

        if self.cfg.ota_firmware_url:
            manifest = {
                "update_available": True,
                "version": self.cfg.ota_firmware_version,
                "url": self.cfg.ota_firmware_url,
                "sha256": self.cfg.ota_firmware_sha256,
                "size": self.cfg.ota_firmware_size,
            }
        else:
            manifest = {
                "update_available": False,
                "version": self.cfg.ota_firmware_version,
            }

        return web.json_response(manifest)


async def start_admin_api(cfg: Config, ws_server: Any = None) -> web.AppRunner:
    """Starts the Admin API on the configured admin_host and admin_port."""
    admin = AdminAPI(cfg, ws_server)
    runner = web.AppRunner(admin.app)
    await runner.setup()
    site = web.TCPSite(runner, cfg.admin_host, cfg.admin_port)
    await site.start()
    log.info("Admin API running at http://%s:%d (auth required)", cfg.admin_host, cfg.admin_port)
    return runner

