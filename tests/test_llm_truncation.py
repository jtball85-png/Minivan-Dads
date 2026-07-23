"""Regression tests for the 2026-07-23 empty-output incident: with adaptive
thinking, a response can hit max_tokens with all budget spent on thinking and
near-zero text — the storefront agent filed a 2-byte report and ingest wrote
a 0-byte agenda. Truncation must raise; implausibly-short output must never
be written to HQ."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from brain.llm import LLM, LLMTruncated, _check_not_truncated


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 8192
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeResponse:
    stop_reason: str
    content: list = field(default_factory=list)
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeClientMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        return self._responses.pop(0)


def make_llm(responses):
    llm = LLM.__new__(LLM)   # skip __init__ (no API key needed) — same
    llm.config = type("C", (), {"model": "test"})()          # pattern as
    llm.client = type("K", (), {})()                         # test_llm_tools
    llm.client.messages = FakeClientMessages(responses)
    llm.hq = None
    llm.command = "test"
    return llm


class TestCheckNotTruncated:
    def test_max_tokens_stop_reason_raises(self):
        with pytest.raises(LLMTruncated, match="8192-token cap"):
            _check_not_truncated(FakeResponse(stop_reason="max_tokens"), 8192)

    def test_normal_stop_reason_passes(self):
        _check_not_truncated(FakeResponse(stop_reason="end_turn"), 8192)


class TestCallPaths:
    def test_call_raises_on_truncation_instead_of_returning_partial(self):
        llm = make_llm([FakeResponse(stop_reason="max_tokens",
                                     content=[FakeTextBlock("partial…")])])
        with pytest.raises(LLMTruncated):
            llm.call([], "go", max_tokens=8192)

    def test_call_with_web_search_raises_on_truncation(self):
        llm = make_llm([FakeResponse(stop_reason="max_tokens", content=[])])
        with pytest.raises(LLMTruncated):
            llm.call_with_web_search([], "go", max_tokens=8192)

    def test_call_returns_text_when_complete(self):
        llm = make_llm([FakeResponse(stop_reason="end_turn",
                                     content=[FakeTextBlock("full report")])])
        assert llm.call([], "go", max_tokens=8192) == "full report"


class TestEmptyOutputNeverWritten:
    def test_ingest_refuses_implausibly_short_agenda(self, monkeypatch):
        from brain import meeting as meeting_mod
        from brain.config import load_config
        from tests.fake_llm import FakeLLM

        class FakeHQ:
            def current_week_key(self):
                return "2026-W30"
            def last_meeting_date(self):
                return None
            def week_key_for_date(self, d):
                return "2026-W29"
            def discover_reports(self, since):
                return {"storefront": ["r"]}
            def write_agenda(self, *a, **k):
                raise AssertionError("empty agenda must never be written")

        monkeypatch.setattr(meeting_mod, "build_system_blocks",
                            lambda *a, **k: [])
        with pytest.raises(RuntimeError, match="not a plausible"):
            meeting_mod.run_ingest(FakeHQ(), FakeLLM(responses=["\n"]),
                                   load_config(), print_fn=lambda *a: None)

    def test_agent_refuses_short_report(self, monkeypatch, tmp_path):
        # run_agent with an LLM whose search call returns near-nothing must
        # exit 1 and write NO report file.
        from brain import agent as agent_mod
        from brain.config import load_config

        config = load_config()
        dept = "storefront"

        class TinyLLM:
            def call_with_web_search(self, *a, **k):
                return "  \n"

        class FakeHQ:
            def current_week_key(self):
                return "2026-W30"
            def read_directive(self, d):
                return "directive"
            def latest_report_week(self, d):
                return None
            def read_report(self, d, w):
                return None
            def read_company_charter(self):
                return "charter"
            def read_tiers(self):
                return "tiers"
            def write_report(self, *a, **k):
                raise AssertionError("empty report must never be written")

        rc = agent_mod.run_agent(dept, config, FakeHQ(), TinyLLM(),
                                 print_fn=lambda *a, **k: None)
        assert rc == 1
