"""
server/tests/test_intents.py — Unit tests for fast-path intent matching and execution.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from anima_server.core.metrics import TurnLatency
from anima_server.core.sentinel import END_OF_RESPONSE
from anima_server.pipeline import intents
from anima_server.pipeline.llm import llm_stage


class DummySession:
    def __init__(self, fast_path=True):
        self.cfg = MagicMock()
        self.cfg.fast_path_intents = fast_path
        self.cfg.max_tool_rounds = 2
        self.cfg.history_turns = 5
        self.current_turn = 1
        self.history = []
        self.llm_q = asyncio.Queue()
        self.token_q = asyncio.Queue()
        self.metrics = MagicMock()
        self.latency = TurnLatency(turn=1)
        self.scope = MagicMock()
        self.scope.is_cancelled = MagicMock(return_value=False)
        self.provider = MagicMock()
        self.provider.stream = MagicMock()
        self.tools = MagicMock()
        self.tools.specs = MagicMock(return_value=[])
        self.tools.invoke = AsyncMock(return_value='{"status": "ok"}')
        self.device_volume = 50

    def is_stale(self, turn: int) -> bool:
        return turn != self.current_turn

    def cancel_turn(self, reason: str) -> None:
        pass


def test_intent_matching_patterns():
    # 1. Volume commands
    hit = intents.match("volume up", None)
    assert hit is not None
    assert hit.name == "volume_rel"
    assert hit.args["delta"] == 10

    hit = intents.match("Turn the volume up!", None)
    assert hit is not None
    assert hit.name == "volume_rel"
    assert hit.args["delta"] == 10

    hit = intents.match("volume down.", None)
    assert hit is not None
    assert hit.name == "volume_rel"
    assert hit.args["delta"] == -10

    hit = intents.match("set volume to 30", None)
    assert hit is not None
    assert hit.name == "volume_set"
    assert hit.args["level"] == 30
    assert hit.reply == "Volume 30."

    hit = intents.match("set the volume to 100 percent", None)
    assert hit is not None
    assert hit.args["level"] == 100

    # 2. Lamp commands
    hit = intents.match("turn on the lamp", None)
    assert hit is not None
    assert hit.name == "lamp_set"
    assert hit.args["on"] is True
    assert hit.reply == "Done."

    hit = intents.match("switch off the light?", None)
    assert hit is not None
    assert hit.name == "lamp_set"
    assert hit.args["on"] is False

    # 3. Time command
    hit = intents.match("what time is it?", None)
    assert hit is not None
    assert hit.name == "time_now"

    hit = intents.match("tell me the time", None)
    assert hit is not None
    assert hit.name == "time_now"

    # 4. Stop command
    hit = intents.match("stop", None)
    assert hit is not None
    assert hit.name == "stop"

    hit = intents.match("be quiet!", None)
    assert hit is not None
    assert hit.name == "stop"

    # 5. Non-intent utterances -> None (must go to LLM)
    assert intents.match("What is the capital of France?", None) is None
    assert intents.match("Tell me a story about a dragon.", None) is None
    assert intents.match("Good morning ANIMA", None) is None


@pytest.mark.asyncio
async def test_intent_run_volume_set():
    session = DummySession()
    hit = intents.match("set volume to 30", session)
    assert hit is not None

    await intents.run(hit, session, turn=1)
    session.tools.invoke.assert_awaited_once()
    assert session.device_volume == 30

    # Verify canned reply pushed to token_q
    tokens = []
    while not session.token_q.empty():
        turn, item = await session.token_q.get()
        assert turn == 1
        tokens.append(item)

    assert tokens == ["Volume 30.", END_OF_RESPONSE]


@pytest.mark.asyncio
async def test_intent_run_lamp_set():
    session = DummySession()
    hit = intents.match("turn on the lamp", session)
    assert hit is not None

    await intents.run(hit, session, turn=1)
    session.tools.invoke.assert_awaited_once()

    tokens = []
    while not session.token_q.empty():
        _, item = await session.token_q.get()
        tokens.append(item)

    assert tokens == ["Done.", END_OF_RESPONSE]


@pytest.mark.asyncio
async def test_intent_run_time_now():
    session = DummySession()
    session.tools.invoke = AsyncMock(return_value='{"time": "07:30 PM"}')
    hit = intents.match("what time is it", session)
    assert hit is not None

    await intents.run(hit, session, turn=1)
    tokens = []
    while not session.token_q.empty():
        _, item = await session.token_q.get()
        tokens.append(item)

    assert tokens == ["It is 07:30 PM.", END_OF_RESPONSE]


@pytest.mark.asyncio
async def test_llm_stage_skips_provider_on_intent():
    session = DummySession(fast_path=True)
    task = asyncio.create_task(llm_stage(session))

    try:
        # Feed fast-path intent
        await session.llm_q.put((1, "set volume to 40"))
        await asyncio.sleep(0.05)

        # Provider must NOT have been called
        assert not session.provider.stream.called
        session.tools.invoke.assert_awaited_once()

        tokens = []
        while not session.token_q.empty():
            _, item = await session.token_q.get()
            tokens.append(item)
        assert tokens == ["Volume 40.", END_OF_RESPONSE]

    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_llm_stage_calls_provider_when_intent_disabled():
    session = DummySession(fast_path=False)

    async def fake_stream(*args, **kwargs):
        from anima_server.providers.base import TextDelta
        yield TextDelta("Adjusted volume to 40.")

    session.provider.stream = fake_stream
    task = asyncio.create_task(llm_stage(session))

    try:
        await session.llm_q.put((1, "set volume to 40"))
        await asyncio.sleep(0.05)

        # Provider WAS called because fast-path was disabled
        tokens = []
        while not session.token_q.empty():
            _, item = await session.token_q.get()
            tokens.append(item)
        assert "Adjusted volume to 40." in tokens

    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
