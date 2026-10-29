"""
server/anima_server/providers/base.py — LLM Provider interface and stream event types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Protocol

from anima_server.core.turn import TurnScope


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]


@dataclass
class Done:
    reason: str


class LLMProvider(Protocol):
    async def validate(self) -> None:
        """Validates credentials and confirms model availability at server startup."""
        ...

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None,
        scope: TurnScope,
    ) -> AsyncIterator[TextDelta | ToolCall | Done]:
        """Streams completion tokens or tool calls bound to a TurnScope."""
        ...

