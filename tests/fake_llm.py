"""A scripted LLM double: returns queued responses in order and records
every call (system blocks + user message) for assertions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMCall:
    system_blocks: list
    user_message: str
    max_tokens: int


@dataclass
class FakeLLM:
    responses: list[str] = field(default_factory=list)
    calls: list[LLMCall] = field(default_factory=list)

    def call(self, system_blocks, user_message, max_tokens=1024):
        self.calls.append(LLMCall(system_blocks, user_message, max_tokens))
        if not self.responses:
            raise AssertionError(f"FakeLLM ran out of scripted responses (call #{len(self.calls)})")
        return self.responses.pop(0)
