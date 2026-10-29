"""
server/anima_server/core/turn.py — TurnScope implementation.

Implements rule T6: Long-running operations are bound to a TurnScope
and must stop when cancelled.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine, Set

log = logging.getLogger("anima.turn")


class TurnScope:
    """Manages tasks and cancellation bound to a single turn."""

    def __init__(self, turn: int):
        self.turn = turn
        self.cancelled = asyncio.Event()
        self.tasks: Set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any], name: str | None = None) -> asyncio.Task[Any] | None:
        """Spawns a tracked task bound to this turn scope if an event loop is running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return None

        t = loop.create_task(coro, name=name or f"turn-{self.turn}")
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)
        return t

    def cancel(self) -> None:
        """Cancels all active tasks in this turn scope."""
        if self.cancelled.is_set():
            return
        self.cancelled.set()
        for t in list(self.tasks):
            if not t.done():
                t.cancel()

    def is_cancelled(self) -> bool:
        return self.cancelled.is_set()
