"""Thin wrapper around the Anthropic SDK. No prompt assembly or business
logic here — that lives in prompts.py and main.py."""

from __future__ import annotations

from anthropic import Anthropic

from brain.config import BrainConfig


class LLM:
    def __init__(self, config: BrainConfig):
        self.config = config
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    def call(self, system_blocks: list[dict], user_message: str, max_tokens: int) -> str:
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text")

    def call_with_web_search(self, system_blocks: list[dict], user_message: str,
                             max_tokens: int, max_searches: int = 8) -> str:
        """One research turn with the server-side web_search tool: the API
        executes searches itself. Long turns can pause (stop_reason
        'pause_turn'); we hand the partial turn back until it completes.
        Used by department agents — the brain's own commands never search."""
        messages = [{"role": "user", "content": user_message}]
        collected: list[str] = []
        while True:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                system=system_blocks,
                messages=messages,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_searches,
                }],
            )
            collected.extend(
                block.text for block in response.content if block.type == "text"
            )
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
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
