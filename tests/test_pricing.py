"""Cost math: per-call pricing and the weekly-burn / per-command summary."""

from __future__ import annotations

import pytest

from brain.models import LLMUsageRecord
from brain.pricing import cost_for_usage, summarize_usage


class TestCostForUsage:
    def test_known_model_uses_its_own_rates(self):
        # claude-sonnet-5: $2.00 in / $10.00 out per 1M tokens.
        cost = cost_for_usage("claude-sonnet-5", input_tokens=1_000_000, output_tokens=0)
        assert cost == 2.00

    def test_output_tokens_priced_separately(self):
        cost = cost_for_usage("claude-sonnet-5", input_tokens=0, output_tokens=1_000_000)
        assert cost == 10.00

    def test_cache_read_is_cheaper_than_full_input(self):
        full = cost_for_usage("claude-sonnet-5", input_tokens=1_000_000, output_tokens=0)
        cached = cost_for_usage("claude-sonnet-5", input_tokens=0, output_tokens=0,
                                cache_read_input_tokens=1_000_000)
        assert cached < full

    def test_unknown_model_falls_back_instead_of_raising(self):
        cost = cost_for_usage("claude-model-from-the-future", input_tokens=1000, output_tokens=1000)
        assert cost > 0


class TestSummarizeUsage:
    def test_empty_records_summarize_to_zero(self):
        summary = summarize_usage([])
        assert summary == {"total_cost": 0.0, "total_tokens": 0, "calls": 0, "by_command": []}

    def test_totals_and_per_command_breakdown(self):
        records = [
            LLMUsageRecord("2026-07-17T10:00:00", "ask", "claude-sonnet-5", 1000, 500),
            LLMUsageRecord("2026-07-17T11:00:00", "ask", "claude-sonnet-5", 2000, 1000),
            LLMUsageRecord("2026-07-17T12:00:00", "ingest", "claude-sonnet-5", 5000, 2000),
        ]
        summary = summarize_usage(records)

        assert summary["calls"] == 3
        assert summary["total_tokens"] == 1000 + 500 + 2000 + 1000 + 5000 + 2000
        expected = sum(cost_for_usage(r.model, r.input_tokens, r.output_tokens) for r in records)
        assert summary["total_cost"] == pytest.approx(expected)

        by_command = {e["command"]: e for e in summary["by_command"]}
        assert by_command["ask"]["calls"] == 2
        assert by_command["ingest"]["calls"] == 1
        # Priciest command first — ingest's 5000+2000 tokens beat ask's combined 4500.
        assert summary["by_command"][0]["command"] == "ingest"
