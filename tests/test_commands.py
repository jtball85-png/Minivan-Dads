"""Command-bar endpoint tests: ingest, meeting flow, consult, directive,
agent, help — FakeLLM only."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from brain.dashboard.app import create_app
from brain.dashboard.chat import register_chat_routes
from brain.meeting import MeetingSession, render_rulings
from brain.models import MeetingRuling
from tests.fake_llm import FakeLLM


class DashFakeLLM(FakeLLM):
    def stream(self, system_blocks, user_message, max_tokens=1024):
        text = self.call(system_blocks, user_message, max_tokens)
        for i in range(0, len(text), 9):
            yield text[i:i + 9]

    def call_with_web_search(self, system_blocks, user_message,
                             max_tokens=8192, max_searches=8):
        return self.call(system_blocks, user_message, max_tokens)


AGENDA = """# Board Meeting Agenda — WEEK

## Department Syntheses

### market_intel

The department found competitors circling and quantified trademark costs.

## Proposed Decisions

#### Decision: Approve the sticker
- Recommendation: Ship it.
- Checklist: money=no, brand=no, legal=no, irreversible=no
- Tag: [BRAIN DECIDES]

#### Decision: File the trademark
- Recommendation: File now.
- Checklist: money=yes, brand=yes, legal=yes, irreversible=no
- Tag: [CEO REQUIRED]

## Escalation Triage

### Urgent
- None.
"""

SYNTHESIS = """## Minutes

The meeting happened.

## Decision Log Entries

### Approve the sticker
- Rationale: fine. Dissents: none
- Decided by: brain (ratified at board meeting)
- Affected departments: none

## Directive Updates

None.

## Resolved Escalations

None.
"""


def parse_sse(text):
    return [json.loads(line[6:]) for line in text.split("\n\n") if line.startswith("data: ")]


@pytest.fixture
def env(config, hq, tmp_hq_root):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nLast updated: 2026-07-16\n\n"
        "## Tier\n\nTier 0 — Read-only\n\n## Status\n\nactive\n", encoding="utf-8"
    )
    (tmp_hq_root / "directives" / "creative.md").write_text("# D", encoding="utf-8")
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    for name in ("system_core.md", "ask.md", "ingest.md", "meeting_synthesis.md",
                 "discussion.md", "consult.md", "directive.md", "agent_core.md",
                 "boardroom_participant.md"):
        (prompts / name).write_text(f"# {name}", encoding="utf-8")
    return config, hq


def make_client(env, responses):
    config, hq = env
    llm = DashFakeLLM(responses=responses)
    app = create_app(config, hq)
    register_chat_routes(app, config, hq, make_llm=lambda: llm)
    return TestClient(app), llm


class TestIngestCommand:
    def test_writes_agenda_and_reports_summary(self, env, hq):
        client, _ = make_client(env, [AGENDA])
        response = client.post("/api/command/ingest")
        events = parse_sse(response.text)
        final = events[-1]
        assert final["done"] is True
        assert final["decisions"] == 2
        agenda_path = hq.root / "meetings" / f"{hq.current_week_key()}-agenda.md"
        assert agenda_path.exists()
        # The CEO must be SHOWN the agenda, not a receipt for it.
        assert "Approve the sticker" in final["agenda"]


class TestMeetingFlow:
    def _start(self, client):
        return client.post("/api/meeting/start").json()

    def test_start_requires_agenda(self, env):
        client, _ = make_client(env, [])
        assert client.post("/api/meeting/start").status_code == 404

    def test_full_flow_writes_records(self, env, hq):
        config, _ = env
        hq.write_agenda(hq.current_week_key(), AGENDA)
        client, _ = make_client(env, [SYNTHESIS])

        data = self._start(client)
        assert [i["title"] for i in data["items"]] == ["Approve the sticker", "File the trademark"]
        assert data["items"][1]["tag"] == "CEO REQUIRED"
        # Briefing = evidence before rulings: syntheses + triage, no decision blocks
        assert "competitors circling" in data["briefing"]
        assert "Escalation Triage" in data["briefing"]
        assert "#### Decision" not in data["briefing"]

        assert client.post("/api/meeting/ruling",
                           json={"item_id": 0, "action": "approve"}).json() == {"recorded": True}
        assert client.post("/api/meeting/ruling",
                           json={"item_id": 1, "action": "modify", "note": "file next week"}).status_code == 200

        result = client.post("/api/meeting/close", json={"ratifications": {}}).json()
        assert result["decisions"] == 1
        assert result["escalations_resolved"] == 0
        assert hq.read_decisions()[-1].title == "Approve the sticker"
        minutes = (hq.root / "meetings" / f"{hq.current_week_key()}-minutes.md").read_text(encoding="utf-8")
        assert "The meeting happened." in minutes
        # Session cleared
        assert client.post("/api/meeting/ruling",
                           json={"item_id": 0, "action": "approve"}).status_code == 409

    def test_discuss_records_on_item(self, env, hq):
        hq.write_agenda(hq.current_week_key(), AGENDA)
        client, llm = make_client(env, ["sidebar counsel", SYNTHESIS])
        self._start(client)
        response = client.post("/api/meeting/discuss", json={"item_id": 0, "text": "is this risky?"})
        assert parse_sse(response.text)[0]["reply"] == "sidebar counsel"
        # The discussion rides into the synthesis call's rulings text
        client.post("/api/meeting/ruling", json={"item_id": 0, "action": "approve"})
        client.post("/api/meeting/close", json={"ratifications": {}})
        synth_call = llm.calls[-1]
        assert "is this risky?" in synth_call.user_message
        assert "sidebar counsel" in synth_call.user_message

    def test_double_start_409s(self, env, hq):
        hq.write_agenda(hq.current_week_key(), AGENDA)
        client, _ = make_client(env, [])
        self._start(client)
        assert client.post("/api/meeting/start").status_code == 409
        assert client.post("/api/meeting/abandon").json() == {"abandoned": True}
        assert client.post("/api/meeting/start").status_code == 200


class TestConsult:
    def test_streams_and_flags_dormant(self, env):
        client, llm = make_client(env, ["From my desk: nothing new."])
        response = client.post("/api/consult",
                               json={"department": "creative", "message": "any badge ideas?"})
        events = parse_sse(response.text)
        text = "".join(e.get("delta", "") for e in events)
        assert text == "From my desk: nothing new."
        assert events[-1]["advisory"] is True  # creative is dormant
        # No HQ writes: consult is conversation only
        assert llm.calls[0].system_blocks[1]["text"].startswith("You are DORMANT")

    def test_active_department_not_advisory(self, env):
        client, _ = make_client(env, ["Active answer."])
        response = client.post("/api/consult",
                               json={"department": "market_intel", "message": "status?"})
        assert parse_sse(response.text)[-1]["advisory"] is False

    def test_unknown_department_404(self, env):
        client, _ = make_client(env, [])
        assert client.post("/api/consult",
                           json={"department": "nobody", "message": "hi"}).status_code == 404


class TestDirectiveCommand:
    DRAFT = "Summary of changes.\n\n```markdown\n# Directive: Market Intel\n\nLast updated: 2026-07-16\n\n## Tier\n\nTier 0 — Read-only\n\n## Status\n\nactive\n\n## Standing orders\n\nWatch Reddit too.\n```\n"

    def test_draft_and_confirm(self, env, hq):
        client, _ = make_client(env, [self.DRAFT])
        data = client.post("/api/command/directive",
                           json={"department": "market_intel", "changes": "add Reddit"}).json()
        assert data["writable"] is True
        assert "Watch Reddit too." not in hq.read_directive("market_intel")

        result = client.post("/api/command/directive/confirm",
                             json={"department": "market_intel"}).json()
        assert "written" in result
        assert "Watch Reddit too." in hq.read_directive("market_intel")
        # Draft consumed — second confirm 409s
        assert client.post("/api/command/directive/confirm",
                           json={"department": "market_intel"}).status_code == 409

    def test_board_decision_refused(self, env, hq):
        client, _ = make_client(env, ["[REQUIRES BOARD DECISION] Tier changes are board decisions."])
        data = client.post("/api/command/directive",
                           json={"department": "market_intel", "changes": "promote to tier 2"}).json()
        assert data["board_decision_required"] is True
        assert data["writable"] is False
        assert client.post("/api/command/directive/confirm",
                           json={"department": "market_intel"}).status_code == 409


class TestAgentCommand:
    def test_runs_and_streams_lines(self, env, hq):
        report = "# Report\n\n## Findings\n\n1. x\n\n## Changes since last report\n\nFirst.\n\n## Escalations\n\nNone.\n"
        client, _ = make_client(env, [report])
        response = client.post("/api/command/agent", json={"department": "market_intel"})
        events = parse_sse(response.text)
        assert events[-1] == {"done": True, "exit_code": 0}
        assert hq.read_report("market_intel", hq.current_week_key()) is not None

    def test_dormant_refusal_streams_reason(self, env):
        client, _ = make_client(env, [])
        events = parse_sse(client.post("/api/command/agent",
                                       json={"department": "creative"}).text)
        assert any("dormant" in e.get("line", "") for e in events)
        assert events[-1]["exit_code"] == 0


class TestStreamErrorGuard:
    def test_api_failure_mid_stream_surfaces_as_error_event(self, env):
        """An Anthropic 500 (or any exception) inside an SSE generator must
        reach the browser as an {error} event — never a silently dead
        stream. Regression for the invisible ingest failure."""
        class ExplodingLLM(DashFakeLLM):
            def call(self, *a, **k):
                raise RuntimeError("Internal server error (simulated API 500)")

        config, hq = env
        llm = ExplodingLLM()
        app = create_app(config, hq)
        register_chat_routes(app, config, hq, make_llm=lambda: llm)
        client = TestClient(app)

        response = client.post("/api/command/ingest")
        assert response.status_code == 200  # stream opened, then failed
        events = parse_sse(response.text)
        assert any("Internal server error" in e.get("error", "") for e in events)
        assert events[-1]["done"] is True


class TestHelp:
    def test_lists_every_bar_command(self, env):
        client, _ = make_client(env, [])
        help_data = client.get("/api/command/help").json()
        commands = {h["command"] for h in help_data}
        assert {"#status", "#ingest", "#meeting", "#boardroom", "#agent",
                "#directive", "#help", "@department"} <= commands


class TestRenderRulings:
    def test_module_level_render(self):
        text = render_rulings([MeetingRuling(item_title="X", action="approve")])
        assert text == "- X: APPROVE"
