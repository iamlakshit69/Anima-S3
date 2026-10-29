"""
Tests for ANIMA Turn rules (Architecture section 5, T1 to T9).
"""

import asyncio
import pytest
from anima_server.config import Config
from anima_server.core.sentinel import END_OF_RESPONSE
from anima_server.core.turn import TurnScope
from anima_server.transport.protocol import Hello
from anima_server.transport.session import Session


class DummyWs:
    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(data)

    async def close(self, code=1000, reason=""):
        pass


@pytest.fixture
def session():
    cfg = Config()
    hello = Hello(proto=1, device_id="test", last_turn=5)
    return Session(device_id="test", ws=DummyWs(), cfg=cfg, models=None, provider=None, hello=hello)


@pytest.mark.asyncio
async def test_turn_scope_cancellation():
    scope = TurnScope(turn=10)
    assert not scope.is_cancelled()

    async def sample_task():
        await asyncio.sleep(10)

    t = scope.spawn(sample_task())
    assert not t.done()

    scope.cancel()
    assert scope.is_cancelled()
    await asyncio.sleep(0)  # Yield to event loop to process cancellation
    assert t.cancelled()


def test_begin_turn_increments_and_cancels_older(session):
    assert session.current_turn == 5

    # Turn 6 starts
    session.begin_turn(6, "wake_word")
    assert session.current_turn == 6
    assert session.state == "LISTENING"
    assert session.scope is not None
    assert not session.scope.is_cancelled()

    old_scope = session.scope

    # Stale/equal turn ignored
    session.begin_turn(6, "button")
    assert session.current_turn == 6
    assert session.metrics.stale_listen_start == 1

    session.begin_turn(4, "button")
    assert session.current_turn == 6
    assert session.metrics.stale_listen_start == 2

    # Higher turn cancels previous scope
    session.begin_turn(7, "barge_in")
    assert session.current_turn == 7
    assert old_scope.is_cancelled()
    assert not session.scope.is_cancelled()


def test_is_stale_drop_rule(session):
    session.begin_turn(10, "wake_word")
    assert not session.is_stale(10)
    assert session.is_stale(9)
    assert session.is_stale(11)


def test_barge_in_race_late_end_marker_does_not_cancel_new_turn(session):
    """Rule T8: Late turn N end marker never stops turn N+1."""
    session.begin_turn(6, "wake_word")
    session.state = "SPEAKING"

    # User taps (barge in -> turn 7)
    session.begin_turn(7, "barge_in")
    assert session.current_turn == 7
    assert session.state == "LISTENING"

    # Late turn 6 finish event arrives
    session.finish_turn(turn=6, reason="done")
    # State must still be LISTENING for turn 7, not reset to IDLE by late turn 6
    assert session.state == "LISTENING"
    assert session.current_turn == 7
