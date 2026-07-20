"""LLM usage logging: every real API call should be captured and handed to
hq.append_llm_usage(), tagged with the command the LLM instance was built
for. Uses a stub Anthropic client — no real API calls, no API key needed."""

from __future__ import annotations

from dataclasses import dataclass, field

from brain.llm import LLM


@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeResponse:
    content: list
    stop_reason: str = "end_turn"
    usage: FakeUsage = field(default_factory=FakeUsage)
    model: str = "claude-sonnet-5"


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


@dataclass
class FakeHQ:
    logged: list = field(default_factory=list)

    def append_llm_usage(self, record):
        self.logged.append(record)


def make_llm(responses, hq=None, command=None):
    llm = LLM.__new__(LLM)  # skip __init__ — no real Anthropic() / API key needed
    llm.config = type("C", (), {"model": "claude-sonnet-5"})()
    llm.client = FakeClient(messages=FakeMessages(responses=list(responses)))
    llm.hq = hq
    llm.command = command
    return llm


class TestCallLogsUsage:
    def test_call_logs_one_record_tagged_with_command(self):
        hq = FakeHQ()
        llm = make_llm(
            [FakeResponse([TextBlock("hi")], usage=FakeUsage(input_tokens=100, output_tokens=40))],
            hq=hq, command="ask",
        )
        llm.call([], "question", max_tokens=100)

        assert len(hq.logged) == 1
        record = hq.logged[0]
        assert record.command == "ask"
        assert record.model == "claude-sonnet-5"
        assert record.input_tokens == 100
        assert record.output_tokens == 40

    def test_no_hq_means_no_logging_and_no_crash(self):
        # Matches tests/test_llm_tools.py's bypass pattern, which never sets
        # self.hq at all — _log_usage must tolerate the missing attribute.
        llm = LLM.__new__(LLM)
        llm.config = type("C", (), {"model": "claude-sonnet-5"})()
        llm.client = FakeClient(messages=FakeMessages(
            responses=[FakeResponse([TextBlock("hi")])]
        ))
        result = llm.call([], "question", max_tokens=100)
        assert result == "hi"


class TestCallWithWebSearchLogsPerIteration:
    def test_pause_turn_continuation_logs_once_per_api_call(self):
        hq = FakeHQ()
        llm = make_llm(
            [
                FakeResponse([TextBlock("part one ")], stop_reason="pause_turn",
                             usage=FakeUsage(input_tokens=50, output_tokens=20)),
                FakeResponse([TextBlock("part two")], stop_reason="end_turn",
                             usage=FakeUsage(input_tokens=70, output_tokens=30)),
            ],
            hq=hq, command="agent:market_intel",
        )
        result = llm.call_with_web_search([], "question", max_tokens=100)

        assert result == "part one part two"
        assert len(hq.logged) == 2
        assert all(r.command == "agent:market_intel" for r in hq.logged)
        assert [r.output_tokens for r in hq.logged] == [20, 30]


class TestStreamLogsFinalUsage:
    def test_stream_logs_usage_from_final_message(self):
        hq = FakeHQ()
        llm = LLM.__new__(LLM)
        llm.config = type("C", (), {"model": "claude-sonnet-5"})()
        llm.hq = hq
        llm.command = "consult"

        final = FakeResponse([TextBlock("streamed")],
                              usage=FakeUsage(input_tokens=10, output_tokens=5))

        class FakeStream:
            text_stream = ["hel", "lo"]

            def get_final_message(self):
                return final

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class FakeMessagesStream:
            def stream(self, **kwargs):
                return FakeStream()

        llm.client = FakeClient(messages=None)
        llm.client.messages = FakeMessagesStream()

        chunks = list(llm.stream([], "question", max_tokens=100))

        assert chunks == ["hel", "lo"]
        assert len(hq.logged) == 1
        assert hq.logged[0].command == "consult"
        assert hq.logged[0].input_tokens == 10
