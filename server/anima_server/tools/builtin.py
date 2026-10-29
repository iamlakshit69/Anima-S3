"""
server/anima_server/tools/builtin.py — Server-side built-in tools.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict


async def time_now() -> Dict[str, Any]:
    """Returns the current date and time."""
    now_local = datetime.datetime.now()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return {
        "time": now_local.strftime("%I:%M %p"),
        "date": now_local.strftime("%A, %B %d, %Y"),
        "iso": now_utc.isoformat(),
    }
