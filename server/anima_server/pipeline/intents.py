"""
server/anima_server/pipeline/intents.py — Fast-path rule matching to skip LLM round-trip.

Matches high-frequency local commands (volume, lamp, time, stop) with regex
and executes them directly through the tool registry, producing canned spoken replies.
Architecture Section 6.9.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
import uuid

from anima_server.core.sentinel import END_OF_RESPONSE
from anima_server.providers.base import ToolCall

log = logging.getLogger("anima.pipeline.intents")


@dataclass(frozen=True)
class MatchedIntent:
    name: str
    tool_name: Optional[str]
    args: Dict[str, Any]
    reply: Optional[str]


def normalize_text(text: str) -> str:
    """Lowercases, trims, and removes trailing punctuation for intent matching."""
    norm = text.strip().lower()
    norm = re.sub(r"[.?!,;:]+$", "", norm).strip()
    return norm


def match(text: str, session: Any) -> Optional[MatchedIntent]:
    """Matches user transcript against fast-path intent regex rules."""
    norm = normalize_text(text)
    if not norm:
        return None

    # 1. Stop / Cancel / Be quiet
    if re.match(r"^(stop|be quiet|shut up|cancel|hush)$", norm):
        return MatchedIntent(name="stop", tool_name=None, args={}, reply=None)

    # 2. Volume Up
    if re.match(r"^(volume up|turn (the )?volume up|increase (the )?volume)$", norm):
        return MatchedIntent(name="volume_rel", tool_name="set_volume", args={"delta": 10}, reply="Volume up.")

    # 3. Volume Down
    if re.match(r"^(volume down|turn (the )?volume down|decrease (the )?volume|lower (the )?volume)$", norm):
        return MatchedIntent(name="volume_rel", tool_name="set_volume", args={"delta": -10}, reply="Volume down.")

    # 4. Set Volume to N (0 to 100)
    m_vol = re.match(r"^set (the )?volume to (\d+)( percent)?$", norm)
    if m_vol:
        level = max(0, min(100, int(m_vol.group(2))))
        return MatchedIntent(name="volume_set", tool_name="set_volume", args={"level": level}, reply=f"Volume {level}.")

    # 5. Turn on / off the lamp or light
    if re.match(r"^(turn|switch) on (the )?(lamp|light)$", norm):
        return MatchedIntent(name="lamp_set", tool_name="lamp_set", args={"on": True}, reply="Done.")

    if re.match(r"^(turn|switch) off (the )?(lamp|light)$", norm):
        return MatchedIntent(name="lamp_set", tool_name="lamp_set", args={"on": False}, reply="Done.")

    # 6. What time is it
    if re.match(r"^(what time is it|what is the time|tell me the time)$", norm):
        return MatchedIntent(name="time_now", tool_name="time.now", args={}, reply=None)

    return None


async def run(hit: MatchedIntent, session: Any, turn: int) -> None:
    """Executes a matched fast-path intent directly without calling LLM."""
    log.info("Executing fast-path intent: %s (tool=%s)", hit.name, hit.tool_name)
    reply_text: Optional[str] = hit.reply

    if hit.name == "stop":
        session.cancel_turn("fast_path_stop")
        return

    elif hit.name == "volume_rel":
        cur_vol = getattr(session, "device_volume", 70)
        new_vol = max(0, min(100, cur_vol + hit.args["delta"]))
        session.device_volume = new_vol
        call_id = f"fp_{uuid.uuid4().hex[:8]}"
        await session.tools.invoke(turn, ToolCall(id=call_id, name="set_volume", args={"level": new_vol}))

    elif hit.name == "volume_set":
        session.device_volume = hit.args["level"]
        call_id = f"fp_{uuid.uuid4().hex[:8]}"
        await session.tools.invoke(turn, ToolCall(id=call_id, name="set_volume", args={"level": hit.args["level"]}))

    elif hit.name == "lamp_set":
        call_id = f"fp_{uuid.uuid4().hex[:8]}"
        await session.tools.invoke(turn, ToolCall(id=call_id, name="lamp_set", args=hit.args))

    elif hit.name == "time_now":
        call_id = f"fp_{uuid.uuid4().hex[:8]}"
        raw_res = await session.tools.invoke(turn, ToolCall(id=call_id, name="time.now", args={}))
        try:
            parsed = json.loads(raw_res)
            time_str = parsed.get("time", "")
            reply_text = f"It is {time_str}." if time_str else "I couldn't get the time."
        except Exception:
            reply_text = "I couldn't get the current time."

    # Send canned reply to TTS token queue
    if reply_text and not session.is_stale(turn):
        session.latency.mark_once("llm_first_token_at")
        await session.token_q.put((turn, reply_text))
        await session.token_q.put((turn, END_OF_RESPONSE))
