"""
server/anima_server/tools/policy.py — Tool execution policy and safety guards.

Implements Rules R7 & R8:
- Forbidden device capabilities are hardcoded in code and cannot be bypassed.
- Validate tool arguments against JSON Schema.
- Rate limit enforcement.
"""

from __future__ import annotations

import fnmatch
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import jsonschema

log = logging.getLogger("anima.tools.policy")

# Hardcoded forbidden capabilities that can NEVER be exposed to or executed by LLM
FORBIDDEN_ALWAYS: List[str] = [
    "reboot",
    "upgrade_firmware",
    "wifi_*",
    "factory_reset",
    "set_token",
]


@dataclass
class PolicyVerdict:
    ok: bool
    reason: str = ""


class ToolPolicy:
    def __init__(self, allowlist_config: Dict[str, Any] | None = None):
        self.config = allowlist_config or {}
        self.rate_history: Dict[str, List[float]] = {}

    def is_forbidden(self, tool_name: str) -> bool:
        """Returns True if the tool name matches any forbidden pattern."""
        for pat in FORBIDDEN_ALWAYS:
            if fnmatch.fnmatch(tool_name, pat):
                return True
        return False

    def exposed(self, tool_spec: Any) -> bool:
        """Determines if a tool is allowed to be exposed to the LLM."""
        if self.is_forbidden(tool_spec.name):
            return False
        # Only safe tools in v1
        return getattr(tool_spec, "risk", "safe") == "safe"

    def check(self, tool_spec: Any, args: Dict[str, Any]) -> PolicyVerdict:
        """Validates tool execution against policy, schema, and rate limits."""
        if self.is_forbidden(tool_spec.name):
            log.warning("Tool %s refused by hardcoded FORBIDDEN policy", tool_spec.name)
            return PolicyVerdict(ok=False, reason="Tool is permanently forbidden")

        if getattr(tool_spec, "risk", "safe") != "safe":
            return PolicyVerdict(ok=False, reason="Only 'safe' risk class tools permitted in v1")

        # 1. JSON Schema validation
        if hasattr(tool_spec, "params") and tool_spec.params:
            try:
                jsonschema.validate(instance=args, schema=tool_spec.params)
            except jsonschema.ValidationError as ve:
                log.warning("Tool argument validation failed for %s: %s", tool_spec.name, ve.message)
                return PolicyVerdict(ok=False, reason=f"Schema validation error: {ve.message}")

        # 2. Rate limit check
        rate_limit = getattr(tool_spec, "rate_per_min", 30)
        now = time.time()
        window = 60.0

        history = self.rate_history.setdefault(tool_spec.name, [])
        # Prune older than 60s
        self.rate_history[tool_spec.name] = [t for t in history if now - t < window]

        if len(self.rate_history[tool_spec.name]) >= rate_limit:
            log.warning("Tool %s rate limit exceeded (%d/min)", tool_spec.name, rate_limit)
            return PolicyVerdict(ok=False, reason=f"Rate limit exceeded (max {rate_limit}/min)")

        self.rate_history[tool_spec.name].append(now)
        return PolicyVerdict(ok=True)
