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
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nLast updated: 2026-07-16\n\n"
        "## Tier\n\nTier 0 — Read-only\n\n## Status\n\nactive\n",
        encoding="utf-8",
    )
    (tmp_hq_root / "directives" / "creative.md").write_text("# D", encoding="utf-8")
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    for name in ("system_core.md", "ask.md", "boardroom_participant.md",
                 "boardroom_moderator.md", "boardroom_synthesis.md"):
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


# --- live boardroom routes -------------------------------------------------

RECORDS_PLAIN = """## Decision Log Entries

### Adopt September plan
- Rationale: reasons. Dissents: none
- Decided by: CEO
- Affected departments: none

## Directive Updates

None.

## Ruling Summary

Adopted.
"""

RECORDS_TIER_SMUGGLE = """## Decision Log Entries

### Promote market_intel
- Rationale: reasons. Dissents: none
- Decided by: CEO
- Affected departments: market_intel

## Directive Updates

### market_intel

```markdown
# Directive: Market Intel

Last updated: 2026-07-16

## Tier

Tier 2 — Act-within-bounds

## Status

active
```

## Ruling Summary

Promoted.
"""


def open_debate(client, responses_llm):
    """Drive /open with a scripted convene + one position + one rebuttal."""
    response = client.post("/api/boardroom/open",
                           json={"topic": "Sept vs Nov?", "depts": ["market_intel"]})
    assert response.status_code == 200
    return parse_sse(response.text)


class TestBoardroomRoutes:
    def test_open_streams_positions_and_rebuttals(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root, [
            "MI position",            # positions (1 participant)
            "MI rebuttal",            # rebuttal round 1
            "SECOND_ROUND: no",       # moderator calls the question
        ])
        events = open_debate(client, llm)
        assert events[0]["participants"] == [{"department": "market_intel", "advisory": False}]
        speakers = [(e["round"], e["text"]) for e in events if "speaker" in e]
        assert ("positions", "MI position") in speakers
        assert ("rebuttal-1", "MI rebuttal") in speakers
        assert events[-1] == {"done": True, "floor_open": True}

    def test_second_open_409s_while_debate_in_progress(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no"])
        open_debate(client, llm)
        response = client.post("/api/boardroom/open", json={"topic": "another"})
        assert response.status_code == 409

    def test_floor_requires_open_debate(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [])
        assert client.post("/api/boardroom/floor", json={"message": "hi"}).status_code == 409

    def test_floor_exchange_routes_at_dept(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no",
                                   "MI floor answer", "NONE"])
        open_debate(client, llm)
        response = client.post("/api/boardroom/floor",
                               json={"message": "@market_intel why?"})
        events = parse_sse(response.text)
        speakers = [e["speaker"] for e in events if "speaker" in e]
        assert speakers == ["CEO", "market_intel"]

    def test_full_rule_flow_writes_records(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no",
                                   "synthesis text", RECORDS_PLAIN])
        open_debate(client, llm)
        synth = client.post("/api/boardroom/synthesize")
        assert "synthesis text" in "".join(
            e.get("delta", "") for e in parse_sse(synth.text))

        response = client.post("/api/boardroom/rule",
                               json={"ruling": "Adopt it.", "ratifications": {}})
        data = response.json()
        assert data["decisions"] == 1
        assert data["directives_updated"] == []
        assert hq.read_decisions()[-1].title == "Adopt September plan"
        # Session cleared: a new debate can open
        assert client.post("/api/boardroom/floor", json={"message": "x"}).status_code == 409

    def test_tier_ratification_round_trip(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no",
                                   RECORDS_TIER_SMUGGLE])
        open_debate(client, llm)

        # First rule call: needs ratification, nothing written yet
        first = client.post("/api/boardroom/rule",
                            json={"ruling": "Promote.", "ratifications": {}}).json()
        assert first["needs_ratification"][0]["dept"] == "market_intel"
        assert "tier 0 -> 2" in first["needs_ratification"][0]["change"]
        assert "Tier 2" not in hq.read_directive("market_intel")

        # Second call with the answer: applied, one records LLM call total
        records_calls = [c for c in llm.calls if "MODE: records" in c.user_message]
        second = client.post("/api/boardroom/rule",
                             json={"ruling": "Promote.",
                                   "ratifications": {"market_intel": True}}).json()
        assert second["directives_updated"] == ["market_intel"]
        assert "Tier 2" in hq.read_directive("market_intel")
        assert [c for c in llm.calls if "MODE: records" in c.user_message] == records_calls

    def test_tier_ratification_declined_skips_write(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no",
                                   RECORDS_TIER_SMUGGLE])
        open_debate(client, llm)
        client.post("/api/boardroom/rule", json={"ruling": "Promote.", "ratifications": {}})
        data = client.post("/api/boardroom/rule",
                           json={"ruling": "Promote.",
                                 "ratifications": {"market_intel": False}}).json()
        assert data["directives_updated"] == []
        assert any("did not ratify" in w for w in data["warnings"])
        assert "Tier 2" not in hq.read_directive("market_intel")

    def test_status_reports_inactive_by_default(self, config, hq, tmp_hq_root):
        client, _ = make_client(config, hq, tmp_hq_root, [])
        assert client.get("/api/boardroom-status").json() == {"active": False}

    def test_status_reports_active_session_with_transcript(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no"])
        open_debate(client, llm)
        status = client.get("/api/boardroom-status").json()
        assert status["active"] is True
        assert status["participants"] == ["market_intel"]
        assert any(e["text"] == "p" for e in status["transcript"])

    def test_status_after_abandon_is_inactive(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no"])
        open_debate(client, llm)
        client.post("/api/boardroom/abandon")
        assert client.get("/api/boardroom-status").json() == {"active": False}

    def test_abandon_clears_session(self, config, hq, tmp_hq_root):
        client, llm = make_client(config, hq, tmp_hq_root,
                                  ["p", "r", "SECOND_ROUND: no",
                                   "p2", "r2", "SECOND_ROUND: no"])
        open_debate(client, llm)
        assert client.post("/api/boardroom/abandon").json() == {"abandoned": True}
        assert client.post("/api/boardroom/open",
                           json={"topic": "new", "depts": ["market_intel"]}).status_code == 200
