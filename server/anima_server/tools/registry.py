"""
server/anima_server/tools/registry.py — Tool registry, schema conversion, and invocation dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

from anima_server.config import Config
from anima_server.tools.builtin import time_now
from anima_server.tools.policy import ToolPolicy
from anima_server.transport.protocol import ToolCallMsg

log = logging.getLogger("anima.tools.registry")


@dataclass
class ToolEntry:
    name: str
    description: str
    params: Dict[str, Any]
    where: Literal["server", "device"]
    risk: Literal["safe", "confirm"] = "safe"
    rate_per_min: int = 30
    fn: Optional[Callable[..., Any]] = None
    device_name: str = ""


def truncate(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


class ToolRegistry:
    def __init__(self, cfg: Config, session: Any, policy: ToolPolicy | None = None):
        self.cfg = cfg
        self.session = session
        self.policy = policy or ToolPolicy()
        self.server_tools: Dict[str, ToolEntry] = {}
        self.device_tools: Dict[str, ToolEntry] = {}
        self.pending_device_calls: Dict[str, asyncio.Future[Any]] = {}

        self._register_server_tools()

    def _register_server_tools(self) -> None:
        self.server_tools["time.now"] = ToolEntry(
            name="time.now",
            description="Get the current local time and date",
            params={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            where="server",
            risk="safe",
            fn=time_now,
        )

    def register_device_tools(self, tools_list: List[Dict[str, Any]]) -> None:
        """Registers tools advertised by the device in its hello message."""
        self.device_tools.clear()
        for t in tools_list:
            name = t.get("name", "")
            if not name:
                continue
            entry = ToolEntry(
                name=f"device.{name}",
                device_name=name,
                description=t.get("description", f"Device tool {name}"),
                params=t.get("params", {}),
                where="device",
                risk=t.get("risk", "safe"),
                rate_per_min=t.get("rate_per_min", 30),
            )
            self.device_tools[entry.name] = entry

    def specs(self) -> List[Dict[str, Any]]:
        """Returns OpenAI-compatible tool specifications for the LLM."""
        specs = []
        all_tools = list(self.server_tools.values()) + list(self.device_tools.values())
        for tool in all_tools:
            if not self.policy.exposed(tool):
                continue
            specs.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.params or {"type": "object", "properties": {}},
                },
            })
        return specs

    def lookup(self, name: str) -> Optional[ToolEntry]:
        if name in self.server_tools:
            return self.server_tools[name]
        if name in self.device_tools:
            return self.device_tools[name]
        # Also try matching with device. prefix
        if f"device.{name}" in self.device_tools:
            return self.device_tools[f"device.{name}"]
        return None

    def resolve(self, call_id: str, result_msg: Any) -> None:
        """Resolves a pending device tool call future."""
        fut = self.pending_device_calls.get(call_id)
        if fut and not fut.done():
            fut.set_result(result_msg)

    async def invoke(self, turn: int, call: Any) -> str:
        """Executes a tool call (server-side or proxied to device via WebSocket)."""
        spec = self.lookup(call.name)
        if spec is None:
            log.warning("Tool %s not found in registry", call.name)
            return json.dumps({"error": "E_TOOL_DENIED", "why": f"Unknown tool: {call.name}"})

        verdict = self.policy.check(spec, call.args)
        if not verdict.ok:
            return json.dumps({"error": "E_TOOL_DENIED", "why": verdict.reason})

        if spec.where == "server":
            assert spec.fn is not None
            try:
                res = await asyncio.wait_for(spec.fn(**call.args), timeout=2.0)
                return truncate(json.dumps(res))
            except asyncio.TimeoutError:
                return json.dumps({"error": "E_TOOL_TIMEOUT", "why": "Server tool timed out"})
            except Exception as e:
                log.exception("Server tool %s failed: %s", spec.name, e)
                return json.dumps({"error": "E_INTERNAL", "why": str(e)})

        # Device proxy
        loop = asyncio.get_running_loop()
        fut = self.pending_device_calls[call.id] = loop.create_future()
        msg = ToolCallMsg(
            turn=turn,
            id=call.id,
            name=spec.device_name or spec.name,
            args=call.args,
            timeout_ms=self.cfg.tool_timeout_ms,
        )

        try:
            await self.session.send(msg)
            timeout_s = self.cfg.tool_timeout_ms / 1000.0
            device_res = await asyncio.wait_for(fut, timeout=timeout_s)
            res_payload = getattr(device_res, "result", None)
            ok = getattr(device_res, "ok", True)
            err = getattr(device_res, "error", None)
            out = {"ok": ok, "result": res_payload}
            if err:
                out["error"] = err
            return truncate(json.dumps(out))
        except asyncio.TimeoutError:
            log.warning("Device tool call %s (%s) timed out", call.id, spec.name)
            return json.dumps({"error": "E_TOOL_TIMEOUT"})
        finally:
            self.pending_device_calls.pop(call.id, None)

