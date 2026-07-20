"""/api/costs — read-only cost visibility over hq/actions/llm_usage.jsonl.
No model call involved; app.py never imports brain.llm (AST-enforced
elsewhere), so this stays a pure view over logged records."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from brain.dashboard.app import create_app
from brain.models import LLMUsageRecord


def _client(config, hq, tmp_hq_root):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    return TestClient(create_app(config, hq))


def test_no_usage_yet_is_all_zero(config, hq, tmp_hq_root):
    client = _client(config, hq, tmp_hq_root)
    data = client.get("/api/costs").json()

    assert data["this_week"]["total_cost"] == 0.0
    assert data["this_week"]["calls"] == 0
    assert data["all_time_cost"] == 0.0
    assert data["typical_by_command"] == []


def test_this_week_totals_and_breakdown(config, hq, tmp_hq_root):
    today = date.today().isoformat()
    hq.append_llm_usage(LLMUsageRecord(f"{today}T09:00:00", "ask", "claude-sonnet-5", 1000, 500))
    hq.append_llm_usage(LLMUsageRecord(f"{today}T10:00:00", "ingest", "claude-sonnet-5", 5000, 2000))

    client = _client(config, hq, tmp_hq_root)
    data = client.get("/api/costs").json()

    assert data["this_week"]["calls"] == 2
    assert data["this_week"]["total_cost"] > 0
    commands = {e["command"] for e in data["this_week"]["by_command"]}
    assert commands == {"ask", "ingest"}


def test_old_usage_excluded_from_this_week_but_counted_all_time(config, hq, tmp_hq_root):
    long_ago = (date.today() - timedelta(days=90)).isoformat()
    hq.append_llm_usage(LLMUsageRecord(f"{long_ago}T09:00:00", "ask", "claude-sonnet-5", 1000, 500))

    client = _client(config, hq, tmp_hq_root)
    data = client.get("/api/costs").json()

    assert data["this_week"]["calls"] == 0
    assert data["all_time_cost"] > 0
    assert data["typical_by_command"][0]["command"] == "ask"
    assert data["typical_by_command"][0]["avg_cost"] == data["all_time_cost"]
