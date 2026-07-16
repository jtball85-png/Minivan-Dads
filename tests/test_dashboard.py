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
