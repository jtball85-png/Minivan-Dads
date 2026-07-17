"""Dashboard endpoint tests — TestClient over create_app, seeded tmp HQ."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from brain.dashboard.app import create_app
from brain.models import DecisionEntry, EscalationItem


@pytest.fixture
def client(config, hq, tmp_hq_root):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nLast updated: 2026-07-16\n", encoding="utf-8"
    )
    hq.append_decision(DecisionEntry(
        date=date(2026, 7, 16), title="Test decision", rationale="because",
        decided_by="CEO", departments=["market_intel"],
    ))
    hq.append_escalation(EscalationItem(
        id="", raised=date(2026, 7, 16), raised_by="market_intel",
        urgency="urgent", summary="Something urgent",
    ))
    week = hq.current_week_key()
    (tmp_hq_root / "reports" / "market_intel").mkdir(parents=True, exist_ok=True)
    (tmp_hq_root / "reports" / "market_intel" / f"{week}.md").write_text(
        "# Report\nfindings", encoding="utf-8"
    )
    hq.write_boardroom_transcript(week, "test-topic", "# Boardroom\ntranscript body")
    return TestClient(create_app(config, hq))


class TestAttention:
    """'What needs me today' — read-only prioritized CEO task list."""

    def _client(self, config, hq, tmp_hq_root):
        (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
        return TestClient(create_app(config, hq))

    def test_all_clear_when_nothing_pending(self, config, hq, tmp_hq_root):
        client = self._client(config, hq, tmp_hq_root)
        data = client.get("/api/attention").json()
        assert data["all_clear"] is True
        assert data["items"] == []

    def test_urgent_escalation_is_priority_zero(self, config, hq, tmp_hq_root):
        hq.append_escalation(EscalationItem(
            id="", raised=date(2026, 7, 16), raised_by="market_intel",
            urgency="urgent", summary="Competitor using our badge",
        ))
        client = self._client(config, hq, tmp_hq_root)
        items = client.get("/api/attention").json()["items"]
        assert items[0]["kind"] == "urgent_escalation"
        assert items[0]["priority"] == 0
        assert "Competitor using our badge" in items[0]["title"]
        assert items[0]["action_command"].startswith("What should I do about")

    def test_agenda_ready_prompts_hold_meeting(self, config, hq, tmp_hq_root):
        week = hq.current_week_key()
        hq.write_agenda(week, "# Agenda\nstuff")
        client = self._client(config, hq, tmp_hq_root)
        items = client.get("/api/attention").json()["items"]
        kinds = {i["kind"]: i for i in items}
        assert "hold_meeting" in kinds
        assert kinds["hold_meeting"]["action_command"] == "#meeting"

    def test_reports_in_no_agenda_prompts_build(self, config, hq, tmp_hq_root):
        week = hq.current_week_key()
        (tmp_hq_root / "reports" / "market_intel").mkdir(parents=True, exist_ok=True)
        (tmp_hq_root / "reports" / "market_intel" / f"{week}.md").write_text(
            "# Report\nx", encoding="utf-8")
        client = self._client(config, hq, tmp_hq_root)
        items = client.get("/api/attention").json()["items"]
        kinds = {i["kind"]: i for i in items}
        assert "build_agenda" in kinds
        assert kinds["build_agenda"]["action_command"] == "#ingest"

    def test_meeting_held_on_fresh_agenda_is_all_clear(self, config, hq, tmp_hq_root):
        week = hq.current_week_key()
        hq.write_agenda(week, "# Agenda\nstuff")
        hq.write_minutes(week, "# Minutes\nheld")
        client = self._client(config, hq, tmp_hq_root)
        data = client.get("/api/attention").json()
        assert not any(i["kind"] == "hold_meeting" for i in data["items"])
        assert data["all_clear"] is True

    def test_stale_agenda_prompts_refresh_not_meeting(self, config, hq, tmp_hq_root):
        """The live bug: an agenda + minutes exist, but a NEW escalation
        arrived afterward that the agenda never mentions. Holding a meeting
        on it would miss the item — the right action is to refresh."""
        week = hq.current_week_key()
        hq.write_agenda(week, "# Agenda\n(built before the new item)")
        hq.write_minutes(week, "# Minutes\nheld")
        eid = hq.append_escalation(EscalationItem(
            id="", raised=date(2026, 7, 16), raised_by="market_intel",
            urgency="normal", summary="arrived after the agenda"))
        client = self._client(config, hq, tmp_hq_root)
        items = client.get("/api/attention").json()["items"]
        build = [i for i in items if i["kind"] == "build_agenda"]
        assert build and build[0]["action_command"] == "#ingest"
        assert "Refresh" in build[0]["action_label"]
        assert not any(i["kind"] == "hold_meeting" for i in items)
        assert eid not in "".join(  # sanity: the agenda really doesn't cover it
            (hq.root / "meetings" / f"{week}-agenda.md").read_text(encoding="utf-8"))

    def test_open_items_drive_build_agenda_and_urgent_sorts_first(self, config, hq, tmp_hq_root):
        hq.append_escalation(EscalationItem(
            id="", raised=date(2026, 7, 16), raised_by="market_intel",
            urgency="urgent", summary="urgent one"))
        hq.append_escalation(EscalationItem(
            id="", raised=date(2026, 7, 16), raised_by="market_intel",
            urgency="normal", summary="normal one"))
        client = self._client(config, hq, tmp_hq_root)
        items = client.get("/api/attention").json()["items"]
        assert items[0]["kind"] == "urgent_escalation"
        build = [i for i in items if i["kind"] == "build_agenda"]
        assert build and "2 open item(s)" in build[0]["detail"]
        assert [i["priority"] for i in items] == sorted(i["priority"] for i in items)


class TestOverview:
    def test_counts_match_seeded_hq(self, client):
        data = client.get("/api/overview").json()
        assert data["stats"]["open_escalations"] == 1
        assert data["stats"]["urgent_escalations"] == 1
        assert data["stats"]["decisions_logged"] == 1
        assert data["stats"]["reports_filed"] == 1  # market_intel (active) filed
        assert data["escalations"][0]["summary"] == "Something urgent"
        assert data["recent_decisions"][0]["title"] == "Test decision"

    def test_agenda_absent_is_null(self, client):
        assert client.get("/api/overview").json()["this_week_agenda"] is None


class TestDepartments:
    def test_lists_all_configured_departments(self, client, config):
        data = client.get("/api/departments").json()
        assert {d["name"] for d in data} == set(config.departments)

    def test_detail_returns_directive_and_report(self, client):
        data = client.get("/api/departments/market_intel").json()
        assert "Directive: Market Intel" in data["directive"]
        assert "findings" in data["latest_report"]
        assert data["actions"] == []

    def test_unknown_department_404s(self, client):
        assert client.get("/api/departments/nonsense").status_code == 404

    def test_git_history_degrades_to_empty_outside_repo(self, client):
        data = client.get("/api/departments/market_intel").json()
        assert data["directive_history"] == []  # tmp dir isn't a git repo


class TestBoardroom:
    def test_lists_transcripts(self, client):
        data = client.get("/api/boardroom").json()
        assert len(data) == 1
        assert data[0]["slug"] == "test-topic"

    def test_fetches_transcript_content(self, client):
        filename = client.get("/api/boardroom").json()[0]["filename"]
        data = client.get(f"/api/boardroom/{filename}").json()
        assert "transcript body" in data["content"]

    def test_path_traversal_rejected(self, client):
        assert client.get("/api/boardroom/..%2F..%2Fcharter%2Fcompany.md").status_code == 404
        assert client.get("/api/boardroom/company.md").status_code == 404


class TestCommands:
    def test_every_cli_subcommand_present(self, client):
        from brain.main import build_parser

        parser = build_parser()
        cli_commands = set(parser._subparsers._group_actions[0].choices)
        api_commands = {c["name"] for c in client.get("/api/commands").json()}
        assert api_commands == cli_commands  # drift guard

    def test_full_help_included(self, client):
        cmds = {c["name"]: c for c in client.get("/api/commands").json()}
        assert "agenda" in cmds["ingest"]["full_help"]


class TestIsolation:
    def test_dashboard_never_imports_llm(self):
        """The dashboard is a read-only view: no model calls, ever. Chat
        surfaces attach in a later increment via their own module."""
        import ast

        import brain.dashboard.app as app_module

        tree = ast.parse(open(app_module.__file__, encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                imported.update(f"{node.module}.{a.name}" for a in node.names)
        assert not any(name.startswith("brain.llm") for name in imported), imported

    def test_index_serves_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "CEO CONSOLE" in response.text
