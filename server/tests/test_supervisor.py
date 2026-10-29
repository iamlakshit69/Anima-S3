"""
Tests for Stage Supervisor (Architecture section 6.11).
"""

import asyncio
import pytest
from anima_server.core.supervisor import supervise


class DummySession:
    def __init__(self):
        self.alerts = []
        self.errors = []
        self.closed = False

    async def send_alert(self, level, code, text):
        self.alerts.append((level, code, text))

    async def send_error(self, code, text, fatal=False):
        self.errors.append((code, text, fatal))

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_supervisor_single_crash_restarts():
    session = DummySession()
    attempts = 0

    async def flaky_stage():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Transient crash")
        # Second attempt succeeds and terminates normally
        return

    await supervise("flaky", flaky_stage, session)
    assert attempts == 2
    assert len(session.alerts) == 1
    assert session.alerts[0][1] == "stage_restart"
    assert not session.closed


@pytest.mark.asyncio
async def test_supervisor_crash_threshold_closes_session():
    session = DummySession()
    attempts = 0

    async def crashing_stage():
        nonlocal attempts
        attempts += 1
        raise RuntimeError(f"Permanent crash #{attempts}")

    await supervise("crashing", crashing_stage, session)
    assert attempts == 5
    assert session.closed
    assert len(session.errors) == 1
    assert session.errors[0][0] == "E_INTERNAL"
    assert session.errors[0][2] is True  # fatal

