"""
server/tests/test_admin_api.py — Tests for authenticated Admin API and OTA manifest endpoints.
"""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from anima_server.admin.api import AdminAPI
from anima_server.config import Config


@pytest.fixture
def admin_cfg():
    return Config(
        admin_host="127.0.0.1",
        admin_port=8766,
        admin_token="super-secret-admin-pass-123",
        ota_firmware_version="1.1.0",
        ota_firmware_url="https://ota.anima.lan/firmware-v1.1.0.bin",
        ota_firmware_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        ota_firmware_size=1048576,
    )


@pytest.fixture
async def admin_client():
    clients = []

    async def _create(cfg):
        admin = AdminAPI(cfg)
        server = TestServer(admin.app)
        client = TestClient(server)
        await client.start_server()
        clients.append(client)
        return client

    yield _create
    for c in clients:
        await c.close()


@pytest.mark.asyncio
async def test_admin_api_healthz_and_auth(admin_cfg, admin_client):
    client = await admin_client(admin_cfg)

    # 1. No token -> 401
    resp = await client.get("/healthz")
    assert resp.status == 401
    data = await resp.json()
    assert data["code"] == "E_AUTH"

    # 2. Bad token -> 401
    resp = await client.get("/healthz", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status == 401

    # 3. Valid token -> 200 OK
    headers = {"Authorization": f"Bearer {admin_cfg.admin_token}"}
    resp = await client.get("/healthz", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert "uptime_s" in data
    assert "active_sessions" in data


@pytest.mark.asyncio
async def test_admin_api_metrics(admin_cfg, admin_client):
    client = await admin_client(admin_cfg)
    headers = {"Authorization": f"Bearer {admin_cfg.admin_token}"}

    resp = await client.get("/metrics", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert "uptime_s" in data
    assert "active_sessions" in data


@pytest.mark.asyncio
async def test_admin_api_ota_manifest_available(admin_cfg, admin_client):
    client = await admin_client(admin_cfg)
    headers = {"Authorization": f"Bearer {admin_cfg.admin_token}"}

    resp = await client.get("/ota/manifest?device_id=esp32s3-fake-01", headers=headers)
    assert resp.status == 200
    manifest = await resp.json()

    # Rule R11: Verify manifest parameters
    assert manifest["update_available"] is True
    assert manifest["version"] == "1.1.0"
    assert manifest["url"] == "https://ota.anima.lan/firmware-v1.1.0.bin"
    assert manifest["sha256"] == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    assert manifest["size"] == 1048576


@pytest.mark.asyncio
async def test_admin_api_ota_manifest_no_update(admin_client):
    cfg = Config(
        admin_token="token-xyz",
        ota_firmware_url="",  # No OTA firmware URL configured
    )
    client = await admin_client(cfg)
    headers = {"Authorization": "Bearer token-xyz"}

    resp = await client.get("/ota/manifest", headers=headers)
    assert resp.status == 200
    manifest = await resp.json()
    assert manifest["update_available"] is False
