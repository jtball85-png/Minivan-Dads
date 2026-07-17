"""Tests for LLM.call_with_web_search's client-tool loop (extra_tools +
tool_executor) — a stub Anthropic client, no real API calls, no API key
needed (LLM.__init__ is bypassed entirely)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from brain.llm import LLM


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list
    stop_reason: str


@dataclass
class FakeMessages:
    responses: list
    calls: list = field(default_factory=list)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@dataclass
class FakeClient:
    messages: FakeMessages


def make_llm(responses):
    llm = LLM.__new__(LLM)  # skip __init__ — no real Anthropic() / API key needed
    llm.config = type("C", (), {"model": "fake-model"})()
    llm.client = FakeClient(messages=FakeMessages(responses=list(responses)))
    return llm


class TestPlainTextCompletion:
    def test_no_tools_needed_returns_immediately(self):
        llm = make_llm([FakeResponse([TextBlock("done")], "end_turn")])
        result = llm.call_with_web_search([], "question", max_tokens=100)
        assert result == "done"
        assert len(llm.client.messages.calls) == 1


class TestPauseTurnContinuation:
    def test_pause_turn_continues_and_concatenates_text(self):
        llm = make_llm([
            FakeResponse([TextBlock("part one ")], "pause_turn"),
            FakeResponse([TextBlock("part two")], "end_turn"),
        ])
        result = llm.call_with_web_search([], "question", max_tokens=100)
        assert result == "part one part two"
        assert len(llm.client.messages.calls) == 2


class TestClientToolLoop:
    def test_tool_use_dispatches_to_executor_and_continues(self):
        executed = []

        def executor(name, tool_input):
            executed.append((name, tool_input))
            return {"status": "available", "confidence": "high"}

        llm = make_llm([
            FakeResponse(
                [ToolUseBlock(id="t1", name="check_domain_availability",
                              input={"domain": "minivandads.com"})],
                "tool_use",
            ),
            FakeResponse([TextBlock("minivandads.com is available")], "end_turn"),
        ])
        result = llm.call_with_web_search(
            [], "check the domain", max_tokens=100,
            extra_tools=[{"name": "check_domain_availability"}],
            tool_executor=executor,
        )
        assert result == "minivandads.com is available"
        assert executed == [("check_domain_availability", {"domain": "minivandads.com"})]

        # Second call's messages must include the tool_result addressed to t1
        second_call_messages = llm.client.messages.calls[1]["messages"]
        tool_result_msg = second_call_messages[-1]
        assert tool_result_msg["role"] == "user"
        assert tool_result_msg["content"][0]["type"] == "tool_result"
        assert tool_result_msg["content"][0]["tool_use_id"] == "t1"
        assert "available" in tool_result_msg["content"][0]["content"]

    def test_multiple_tool_use_blocks_in_one_turn(self):
        def executor(name, tool_input):
            return {"handle": tool_input.get("handle"), "status": "checked"}

        llm = make_llm([
            FakeResponse(
                [
                    ToolUseBlock(id="a", name="check_handle_availability",
                                 input={"platform": "etsy", "handle": "mvd"}),
                    ToolUseBlock(id="b", name="check_handle_availability",
                                 input={"platform": "instagram", "handle": "mvd"}),
                ],
                "tool_use",
            ),
            FakeResponse([TextBlock("both checked")], "end_turn"),
        ])
        result = llm.call_with_web_search(
            [], "check handles", max_tokens=100,
            extra_tools=[{"name": "check_handle_availability"}],
            tool_executor=executor,
        )
        assert result == "both checked"
        tool_results = llm.client.messages.calls[1]["messages"][-1]["content"]
        assert {r["tool_use_id"] for r in tool_results} == {"a", "b"}

    def test_tool_use_without_executor_falls_through_and_returns(self):
        """No tool_executor supplied — must not loop forever; returns
        whatever text is present instead of hanging."""
        llm = make_llm([
            FakeResponse([TextBlock("partial")], "tool_use"),
        ])
        result = llm.call_with_web_search([], "q", max_tokens=100)
        assert result == "partial"
        assert len(llm.client.messages.calls) == 1

    def test_tools_list_includes_web_search_plus_extras(self):
        llm = make_llm([FakeResponse([TextBlock("ok")], "end_turn")])
        llm.call_with_web_search(
            [], "q", max_tokens=100,
            extra_tools=[{"name": "check_domain_availability"}],
        )
        tools_sent = llm.client.messages.calls[0]["tools"]
        names = {t.get("name") for t in tools_sent}
        assert "web_search" in names
        assert "check_domain_availability" in names

    def test_backward_compatible_without_extra_tools(self):
        """Existing call sites (agent.py before this change) must work
        unmodified — only web_search in the tools list."""
        llm = make_llm([FakeResponse([TextBlock("ok")], "end_turn")])
        llm.call_with_web_search([], "q", max_tokens=100)
        tools_sent = llm.client.messages.calls[0]["tools"]
        assert len(tools_sent) == 1
        assert tools_sent[0]["name"] == "web_search"
