"""
server/anima_server/core/logger.py — Structured logging setup.
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configures structured root logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Clear existing handlers
    root.handlers.clear()
    root.addHandler(handler)

