"""hq/actions/llm_usage.jsonl — append-only cost telemetry log."""

from __future__ import annotations

from datetime import date

from brain.models import LLMUsageRecord


def test_append_then_read_round_trips(hq):
    record = LLMUsageRecord(
        timestamp="2026-07-17T09:00:00", command="ask", model="claude-sonnet-5",
        input_tokens=1200, output_tokens=400,
        cache_creation_input_tokens=0, cache_read_input_tokens=800,
    )
    hq.append_llm_usage(record)

    records = hq.read_llm_usage()
    assert records == [record]


def test_read_with_no_log_file_returns_empty(hq):
    assert hq.read_llm_usage() == []


def test_multiple_appends_accumulate_in_order(hq):
    first = LLMUsageRecord("2026-07-16T09:00:00", "ask", "claude-sonnet-5", 100, 50)
    second = LLMUsageRecord("2026-07-17T09:00:00", "ingest", "claude-sonnet-5", 500, 200)
    hq.append_llm_usage(first)
    hq.append_llm_usage(second)

    assert hq.read_llm_usage() == [first, second]


def test_since_filters_by_date(hq):
    old = LLMUsageRecord("2026-07-01T09:00:00", "ask", "claude-sonnet-5", 100, 50)
    recent = LLMUsageRecord("2026-07-17T09:00:00", "ask", "claude-sonnet-5", 100, 50)
    hq.append_llm_usage(old)
    hq.append_llm_usage(recent)

    records = hq.read_llm_usage(since=date(2026, 7, 10))
    assert records == [recent]


def test_log_is_append_only_file_mode(hq):
    """Regression guard for the load-bearing rule: appends never rewrite
    history, even across many calls."""
    for i in range(3):
        hq.append_llm_usage(LLMUsageRecord(f"2026-07-1{i}T09:00:00", "ask", "claude-sonnet-5", 10, 5))
    lines = hq.llm_usage_log_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
