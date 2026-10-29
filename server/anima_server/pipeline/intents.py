"""
server/anima_server/pipeline/intents.py — Fast-path rule matching to skip LLM round-trip.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("anima.pipeline.intents")


def match(text: str, session: Any) -> Optional[Any]:
    """Matches text against fast-path intent regex rules. (Phase 4 feature)."""
    return None


async def run(hit: Any, session: Any, turn: int) -> None:
    """Executes a matched fast-path intent directly."""
    pass

