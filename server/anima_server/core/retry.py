"""
server/anima_server/core/retry.py — Retry helpers and fallback tone generator.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, TypeVar

import numpy as np

from anima_server.core.turn import TurnScope

log = logging.getLogger("anima.retry")

T = TypeVar("T")


async def retry_with_backoff(
    coro_factory: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_retries: int = 3,
    initial_delay: float = 0.2,
    backoff_factor: float = 2.0,
    jitter: float = 0.2,
    scope: TurnScope | None = None,
    stage: str = "stage",
    **kwargs: Any,
) -> T:
    """Retries an async callable with exponential backoff and jitter.

    Aborts immediately if the provided TurnScope is cancelled.
    """
    delay = initial_delay
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        if scope and scope.is_cancelled():
            raise asyncio.CancelledError(f"Turn {scope.turn} was cancelled during retry")

        try:
            return await coro_factory(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            last_exc = e
            if attempt == max_retries:
                log.warning("[%s] Retry attempt %d/%d failed permanently: %s", stage, attempt, max_retries, e)
                raise

            sleep_time = delay * (1.0 + random.uniform(-jitter, jitter))
            log.info(
                "[%s] Attempt %d/%d failed (%s). Retrying in %.2fs...",
                stage,
                attempt,
                max_retries,
                e,
                sleep_time,
            )

            # Sleep or break early on cancellation
            if scope:
                try:
                    await asyncio.wait_for(scope.cancelled.wait(), timeout=sleep_time)
                    raise asyncio.CancelledError(f"Turn {scope.turn} cancelled while sleeping in retry")
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(sleep_time)

            delay *= backoff_factor

    assert last_exc is not None
    raise last_exc


def generate_error_tone(sample_rate: int = 24000, duration_s: float = 0.3, freq_hz: float = 440.0) -> np.ndarray:
    """Generates a simple sine wave tone as an int16 array."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    # Sine wave with gentle fade in / fade out
    sine = np.sin(2.0 * np.pi * freq_hz * t) * 0.3
    envelope = np.ones_like(sine)
    fade_len = int(sample_rate * 0.02)  # 20ms fade
    if len(sine) > 2 * fade_len:
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
    return (sine * envelope * 32767).astype(np.int16)

