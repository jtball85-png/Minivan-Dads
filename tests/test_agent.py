"""Department-agent template tests — FakeLLM, no web searches."""

from __future__ import annotations

import pytest

from brain.agent import parse_escalations, run_agent
from tests.fake_llm import FakeLLM


class ResearchFakeLLM(FakeLLM):
    def call_with_web_search(self, system_blocks, user_message,
                             max_tokens=8192, max_searches=8,
                             extra_tools=None, tool_executor=None):
        return self.call(system_blocks, user_message, max_tokens)


REPORT_PLAIN = """# Market Intel Report — WEEK

Filed by: market_intel agent (scheduled run)

## Findings

1. Nothing notable this week.

## Changes since last report

First report; no baseline.

## Escalations

None.
"""

REPORT_WITH_ESCALATIONS = """# Market Intel Report — WEEK

## Findings

1. Competitor using near-identical badge language on Etsy.

## Changes since last report

New threat found.

## Escalations

### ESCALATION
- Urgency: urgent
- Summary: Etsy seller using near-identical badge language; trademark exposure.

### ESCALATION
- Urgency: normal
- Summary: Amazon Merch dad-niche category shifted toward fishing themes.
"""


@pytest.fixture
def agent_env(config, hq, tmp_hq_root):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nWatch the watch list.\n", encoding="utf-8"
    )
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "agent_core.md").write_text("# agent core", encoding="utf-8")
    return config, hq


class TestParseEscalations:
    def test_parses_multiple_blocks(self):
        items = parse_escalations(REPORT_WITH_ESCALATIONS)
        assert items == [
            ("urgent", "Etsy seller using near-identical badge language; trademark exposure."),
            ("normal", "Amazon Merch dad-niche category shifted toward fishing themes."),
        ]

    def test_none_section_yields_nothing(self):
        assert parse_escalations(REPORT_PLAIN) == []


class TestRunAgent:
    def test_unknown_department_exits_1(self, agent_env):
        config, hq = agent_env
        llm = ResearchFakeLLM()
        assert run_agent("nonsense", config, hq, llm, print_fn=lambda s: None) == 1
        assert llm.calls == []

    def test_dormant_department_skips_cleanly(self, agent_env):
        config, hq = agent_env
        llm = ResearchFakeLLM()
        # creative is dormant in the fixture config
        assert run_agent("creative", config, hq, llm, print_fn=lambda s: None) == 0
        assert llm.calls == []

    def test_active_run_writes_weekly_report(self, agent_env):
        config, hq = agent_env
        llm = ResearchFakeLLM(responses=[REPORT_PLAIN])
        assert run_agent("market_intel", config, hq, llm, print_fn=lambda s: None) == 0

        week = hq.current_week_key()
        report = hq.read_report("market_intel", week)
        assert report is not None
        assert "## Findings" in report
        assert hq.read_escalation_queue() == []

    def test_escalations_filed_to_queue(self, agent_env):
        config, hq = agent_env
        llm = ResearchFakeLLM(responses=[REPORT_WITH_ESCALATIONS])
        run_agent("market_intel", config, hq, llm, print_fn=lambda s: None)

        queue = hq.read_escalation_queue()
        assert len(queue) == 2
        assert queue[0].urgency == "urgent"  # urgent sorts first
        assert queue[0].raised_by == "market_intel"

    def test_directive_and_charter_in_context(self, agent_env):
        """The exit-criteria mechanism: the directive is loaded fresh every
        run, so a Monday directive change reaches Thursday's report."""
        config, hq = agent_env
        llm = ResearchFakeLLM(responses=[REPORT_PLAIN])
        run_agent("market_intel", config, hq, llm, print_fn=lambda s: None)

        static = llm.calls[0].system_blocks[0]["text"]
        dynamic = llm.calls[0].system_blocks[1]["text"]
        assert "# Charter" in static
        assert "Watch the watch list." in dynamic

    def test_previous_report_is_memory(self, agent_env):
        config, hq = agent_env
        prev_week = hq.previous_week_key()
        hq.write_report("market_intel", prev_week, "# Old report\nOld finding.")
        llm = ResearchFakeLLM(responses=[REPORT_PLAIN])
        run_agent("market_intel", config, hq, llm, print_fn=lambda s: None)

        dynamic = llm.calls[0].system_blocks[1]["text"]
        assert "Old finding." in dynamic
        assert prev_week in dynamic

    def test_first_run_says_no_previous_report(self, agent_env):
        config, hq = agent_env
        llm = ResearchFakeLLM(responses=[REPORT_PLAIN])
        run_agent("market_intel", config, hq, llm, print_fn=lambda s: None)
        assert "first report" in llm.calls[0].system_blocks[1]["text"].lower()
