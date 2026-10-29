"""
Tests for Device tool proxy and timeout handling (Architecture section 6.10).
"""

import asyncio
import json
import pytest
from anima_server.config import Config
from anima_server.tools.registry import ToolRegistry
from anima_server.transport.protocol import ToolCallMsg, ToolResultMsg


class DummySession:
    def __init__(self):
        self.sent_messages = []

    async def send(self, msg):
        self.sent_messages.append(msg)


@pytest.mark.asyncio
async def test_device_proxy_successful_call():
    cfg = Config(tool_timeout_ms=500)
    session = DummySession()
    reg = ToolRegistry(cfg, session)

    # Register device tool
    reg.register_device_tools([
        {
            "name": "set_volume",
            "description": "Set volume",
            "params": {"type": "object", "properties": {"level": {"type": "integer"}}},
            "risk": "safe",
        }
    ])

    call_obj = type("Call", (), {"name": "set_volume", "args": {"level": 70}, "id": "call_123"})

    async def resolve_later():
        await asyncio.sleep(0.05)
        # Device returns tool.result
        reg.resolve("call_123", ToolResultMsg(turn=1, id="call_123", ok=True, result={"volume": 70}))

    asyncio.create_task(resolve_later())
    res_str = await reg.invoke(turn=1, call=call_obj)

    assert len(session.sent_messages) == 1
    assert isinstance(session.sent_messages[0], ToolCallMsg)
    assert session.sent_messages[0].name == "set_volume"

    res = json.loads(res_str)
    assert res["ok"] is True
    assert res["result"]["volume"] == 70


@pytest.mark.asyncio
async def test_device_proxy_timeout():
    cfg = Config(tool_timeout_ms=50)  # fast 50ms timeout
    session = DummySession()
    reg = ToolRegistry(cfg, session)

    reg.register_device_tools([
        {"name": "lamp_set", "description": "Lamp", "params": {}, "risk": "safe"}
    ])

    call_obj = type("Call", (), {"name": "lamp_set", "args": {}, "id": "call_timeout"})
    # Do not resolve within 50ms
    res_str = await reg.invoke(turn=1, call=call_obj)
    res = json.loads(res_str)
    assert res["error"] == "E_TOOL_TIMEOUT"


@pytest.mark.asyncio
async def test_device_proxy_tool_denied():
    cfg = Config()
    session = DummySession()
    reg = ToolRegistry(cfg, session)

    # Calling an unknown or forbidden tool returns E_TOOL_DENIED
    call_obj = type("Call", (), {"name": "reboot", "args": {}, "id": "call_forbidden"})
    res_str = await reg.invoke(turn=1, call=call_obj)
    res = json.loads(res_str)
    assert res["error"] == "E_TOOL_DENIED"


@pytest.mark.asyncio
async def test_device_proxy_late_result_ignored():
    cfg = Config(tool_timeout_ms=50)
    session = DummySession()
    reg = ToolRegistry(cfg, session)

    reg.register_device_tools([
        {"name": "lamp_set", "description": "Lamp", "params": {}, "risk": "safe"}
    ])

    call_obj = type("Call", (), {"name": "lamp_set", "args": {}, "id": "call_late"})
    # Timed out call
    res_str = await reg.invoke(turn=1, call=call_obj)
    assert json.loads(res_str)["error"] == "E_TOOL_TIMEOUT"

    # Late result arrives after timeout
    # Must not raise or crash
    reg.resolve("call_late", ToolResultMsg(turn=1, id="call_late", ok=True, result={"on": True}))
