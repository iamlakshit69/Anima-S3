"""
Allow running the diagnostics module as:
    python -m anima_server.diagnostics
"""

import asyncio
import sys

from anima_server.diagnostics.anima_check import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

