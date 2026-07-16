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
