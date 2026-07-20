"""Thin wrapper around the Anthropic SDK. No prompt assembly or business
logic here — that lives in prompts.py and main.py."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from anthropic import Anthropic

from brain.config import BrainConfig
from brain.models import LLMUsageRecord


class LLM:
    def __init__(self, config: BrainConfig, hq=None, command: str | None = None):
        self.config = config
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        # Cost telemetry — optional. `hq` writes hq/actions/llm_usage.jsonl;
        # `command` tags every call this instance makes (e.g. "ingest",
        # "agent:market_intel") so the CEO console can show weekly burn and
        # a typical cost per action. Both are None for callers that skip
        # __init__ entirely (see tests/test_llm_tools.py) or don't care.
        self.hq = hq
        self.command = command

    def _log_usage(self, response) -> None:
        hq = getattr(self, "hq", None)
        if hq is None:
            return
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        try:
            hq.append_llm_usage(LLMUsageRecord(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                command=getattr(self, "command", None) or "unknown",
                model=getattr(response, "model", None) or self.config.model,
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            ))
        except OSError:
            pass  # telemetry must never break the actual command

    def call(self, system_blocks: list[dict], user_message: str, max_tokens: int) -> str:
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_message}],
        )
        self._log_usage(response)
        return "".join(block.text for block in response.content if block.type == "text")

    def call_with_web_search(
        self, system_blocks: list[dict], user_message: str,
        max_tokens: int, max_searches: int = 8,
        extra_tools: list[dict] | None = None,
        tool_executor: Callable[[str, dict], dict] | None = None,
    ) -> str:
        """One research turn with the server-side web_search tool: the API
        executes searches itself. Long turns can pause (stop_reason
        'pause_turn'); we hand the partial turn back until it completes.
        Used by department agents — the brain's own commands never search.

        `extra_tools` + `tool_executor` add CLIENT-side tools (e.g. live
        domain/handle checks in brain/tools.py): when the model emits a
        tool_use block for one of these, we run tool_executor(name, input)
        ourselves and feed the result back as a tool_result, then continue
        the turn — same shape as the server tool's pause_turn loop, just
        with us doing the work instead of Anthropic's infrastructure.
        """
        messages = [{"role": "user", "content": user_message}]
        collected: list[str] = []
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }]
        if extra_tools:
            tools.extend(extra_tools)

        while True:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                system=system_blocks,
                messages=messages,
                tools=tools,
            )
            self._log_usage(response)
            collected.extend(
                block.text for block in response.content if block.type == "text"
            )

            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue

            if response.stop_reason == "tool_use" and tool_executor is not None:
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if tool_use_blocks:
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(tool_executor(block.name, block.input)),
                            }
                            for block in tool_use_blocks
                        ],
                    })
                    continue

            return "".join(collected)

    def stream(self, system_blocks: list[dict], user_message: str, max_tokens: int):
        """Yield text deltas as they arrive — for the dashboard's chat
        surfaces. Same request shape as call()."""
        with self.client.messages.stream(
            model=self.config.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            yield from stream.text_stream
            self._log_usage(stream.get_final_message())
