"""
server/anima_server/core/supervisor.py — Pipeline stage supervisor.

Supervises long-running pipeline stages with crash tracking and exponential backoff.
If a stage crashes 5 times within 60 seconds, the session is terminated with E_INTERNAL.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Coroutine

log = logging.getLogger("anima.supervisor")


async def supervise(
    name: str,
    stage_factory: Callable[[], Coroutine[Any, Any, None]],
    session: Any,
) -> None:
    """Supervises a pipeline stage, restarting it on failure up to threshold."""
    backoff = 0.5
    crashes: deque[float] = deque(maxlen=5)

    while True:
        try:
            await stage_factory()
            # If the factory returns normally, exit the supervisor loop
            break
        except asyncio.CancelledError:
            log.debug("Stage %s cancelled", name)
            raise
        except Exception as exc:
            now = time.time()
            log.exception("Stage %s crashed: %s", name, exc)
            crashes.append(now)

            if len(crashes) == 5 and (crashes[-1] - crashes[0] < 60.0):
                log.error("Stage %s exceeded crash threshold (5 in 60s). Terminating session.", name)
                try:
                    await session.send_error(code="E_INTERNAL", text=f"Stage {name} crashed repeatedly", fatal=True)
                    await session.close()
                except Exception:
                    pass
                return

            try:
                await session.send_alert(level="warn", code="stage_restart", text=name)
            except Exception:
                pass

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 10.0)

