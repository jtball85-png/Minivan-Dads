"""Dashboard chat-surface tests (ask streaming + decision logging) — FakeLLM,
no API calls."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from brain.dashboard.app import create_app
from brain.dashboard.chat import register_chat_routes
from tests.fake_llm import FakeLLM


class StreamingFakeLLM(FakeLLM):
    """FakeLLM whose stream() yields the scripted response in small chunks."""

    def stream(self, system_blocks, user_message, max_tokens=1024):
        text = self.call(system_blocks, user_message, max_tokens)
        for i in range(0, len(text), 7):
            yield text[i:i + 7]


def make_client(config, hq, tmp_hq_root, responses):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives" / "market_intel.md").write_text("# D", encoding="utf-8")
    (tmp_hq_root / "directives" / "creative.md").write_text("# D", encoding="utf-8")
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    for name in ("system_core.md", "ask.md"):
        (prompts / name).write_text(f"# {name}", encoding="utf-8")

    llm = StreamingFakeLLM(responses=responses)
    app = create_app(config, hq)
    register_chat_routes(app, config, hq, make_llm=lambda: llm)
    return TestClient(app), llm


def parse_sse(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.split("\n\n") if line.startswith("data: ")]


PLAIN_ANSWER = "Our brand voice is ironic pride with swagger wagon energy."

DECISION_ANSWER = """Yes — expand the watch list.

## Decision Record
- Decision: Expand watch list to Reddit
- Rationale: Coverage gap identified
- Decided by: CEO
- Affected departments: market_intel
"""


class TestAsk:
    def test_streams_answer_in_deltas(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [PLAIN_ANSWER])
        response = client.post("/api/ask", json={"question": "what's our voice?"})
        assert response.status_code == 200
        events = parse_sse(response.text)
        deltas = "".join(e["delta"] for e in events if "delta" in e)
        assert deltas == PLAIN_ANSWER
        assert events[-1]["done"] is True
        assert events[-1]["decision_record"] is None

    def test_decision_record_detected_and_parsed(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [DECISION_ANSWER])
        response = client.post("/api/ask", json={"question": "expand the list?"})
        record = parse_sse(response.text)[-1]["decision_record"]
        assert record["title"] == "Expand watch list to Reddit"
        assert record["departments"] == ["market_intel"]

    def test_empty_question_422(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [])
        assert client.post("/api/ask", json={"question": "  "}).status_code == 422

    def test_full_company_context_loaded(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root, [PLAIN_ANSWER])
        client.post("/api/ask", json={"question": "q"})
        # ask must load charter into the (cached) system block, per the brief
        static_block = llm.calls[0].system_blocks[0]["text"]
        assert "# Charter" in static_block


class TestLogDecision:
    def test_logs_to_hq(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [])
        response = client.post("/api/ask/log-decision", json={
            "title": "Expand watch list to Reddit",
            "rationale": "Coverage gap",
            "decided_by": "CEO",
            "departments": ["market_intel"],
        })
        assert response.json() == {"logged": True}
        decisions = hq.read_decisions()
        assert decisions[-1].title == "Expand watch list to Reddit"
        assert decisions[-1].departments == ["market_intel"]

    def test_read_only_view_works_without_chat_routes(self, config, hq, tmp_hq_root):
        """create_app alone (no register_chat_routes) still serves — the
        console degrades gracefully when the model is unavailable."""
        (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
        client = TestClient(create_app(config, hq))
        assert client.get("/api/overview").status_code == 200
        assert client.post("/api/ask", json={"question": "q"}).status_code in (404, 405)
