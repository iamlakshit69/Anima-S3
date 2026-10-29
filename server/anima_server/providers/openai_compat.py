"""
server/anima_server/providers/openai_compat.py — OpenAI-compatible provider (Groq, Ollama, OpenAI).
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List

from openai import AsyncOpenAI

from anima_server.config import Config
from anima_server.core.turn import TurnScope
from anima_server.providers.base import Done, TextDelta, ToolCall

log = logging.getLogger("anima.provider.openai")


class StartupError(RuntimeError):
    pass


class OpenAICompatProvider:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = AsyncOpenAI(
            base_url=cfg.llm_base_url or None,
            api_key=cfg.llm_api_key or "no-key-set",
        )

    async def validate(self) -> None:
        """Validates connection and verifies that cfg.llm_model is offered."""
        try:
            models_page = await self.client.models.list()
            ids = [m.id for m in models_page.data]
            if self.cfg.llm_model not in ids:
                raise StartupError(
                    f"Model '{self.cfg.llm_model}' not offered by provider at {self.cfg.llm_base_url}. "
                    f"Available models: {', '.join(ids[:15])}{'...' if len(ids) > 15 else ''}"
                )
            log.info("Validated LLM provider at %s (model='%s')", self.cfg.llm_base_url, self.cfg.llm_model)
        except StartupError:
            raise
        except Exception as e:
            raise StartupError(f"Failed to connect to LLM provider at {self.cfg.llm_base_url}: {e}") from e

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None,
        scope: TurnScope,
    ) -> AsyncIterator[TextDelta | ToolCall | Done]:
        """Streams completion tokens and tool calls, respecting TurnScope cancellation."""
        kwargs: Dict[str, Any] = {
            "model": self.cfg.llm_model,
            "messages": messages,
            "stream": True,
            "max_tokens": self.cfg.llm_max_tokens,
            "temperature": self.cfg.llm_temperature,
        }
        if tools:
            kwargs["tools"] = tools

        resp = await self.client.chat.completions.create(**kwargs)
        tool_call_accum: Dict[int, Dict[str, Any]] = {}

        try:
            async for chunk in resp:
                if scope.is_cancelled():
                    log.debug("TurnScope cancelled during LLM stream")
                    break

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 1. Content delta
                if delta.content:
                    yield TextDelta(delta.content)

                # 2. Tool call deltas
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_call_accum:
                            tool_call_accum[idx] = {
                                "id": tc.id or "",
                                "name": (tc.function.name if tc.function and tc.function.name else ""),
                                "args": "",
                            }
                        if tc.id:
                            tool_call_accum[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_call_accum[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_call_accum[idx]["args"] += tc.function.arguments

            # Yield any accumulated tool calls
            for idx in sorted(tool_call_accum.keys()):
                tc_data = tool_call_accum[idx]
                try:
                    args_obj = json.loads(tc_data["args"]) if tc_data["args"] else {}
                except json.JSONDecodeError:
                    args_obj = {"raw": tc_data["args"]}
                yield ToolCall(
                    id=tc_data["id"] or f"call_{idx}",
                    name=tc_data["name"],
                    args=args_obj,
                )

            yield Done(reason="stop")
        finally:
            await resp.close()

