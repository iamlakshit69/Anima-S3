"""
Tests for Tool security policy, schema validation, and rate limiting (Rules R7, R8).
"""

from dataclasses import dataclass
import pytest
from anima_server.tools.policy import ToolPolicy


@dataclass
class DummyTool:
    name: str
    params: dict
    risk: str = "safe"
    rate_per_min: int = 5


def test_forbidden_tools_never_exposed():
    policy = ToolPolicy()
    for forbidden in ["reboot", "upgrade_firmware", "wifi_set_creds", "factory_reset", "set_token"]:
        tool = DummyTool(name=forbidden, params={})
        assert policy.is_forbidden(forbidden)
        assert not policy.exposed(tool)

        verdict = policy.check(tool, {})
        assert not verdict.ok
        assert "forbidden" in verdict.reason.lower()


def test_schema_argument_validation():
    policy = ToolPolicy()
    tool = DummyTool(
        name="set_volume",
        params={
            "type": "object",
            "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
            "required": ["level"],
        },
    )

    # Valid args
    assert policy.check(tool, {"level": 50}).ok

    # Invalid range (exceeds maximum)
    bad_range = policy.check(tool, {"level": 150})
    assert not bad_range.ok
    assert "schema" in bad_range.reason.lower()

    # Invalid type (string instead of int)
    bad_type = policy.check(tool, {"level": "high"})
    assert not bad_type.ok
    assert "schema" in bad_type.reason.lower()

    # Missing required field
    missing = policy.check(tool, {})
    assert not missing.ok
    assert "schema" in missing.reason.lower()


def test_rate_limit_enforced():
    policy = ToolPolicy()
    tool = DummyTool(name="test_tool", params={}, rate_per_min=3)

    # First 3 calls succeed
    assert policy.check(tool, {}).ok
    assert policy.check(tool, {}).ok
    assert policy.check(tool, {}).ok

    # 4th call within 1 minute must be rejected
    v = policy.check(tool, {})
    assert not v.ok
    assert "rate limit" in v.reason.lower()
