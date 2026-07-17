"""The shared department-agent template (roadmap: departments are clones of
one template that reads its directive from HQ and writes reports back).

One scheduled run = one loop: load directive -> load last report (memory) ->
research via web search -> write hq/reports/{dept}/{week}.md -> file any
escalations -> exit. Blast radius of any bug: one bad report.

Phase 2 activates market_intel; later phases activate more departments by
flipping their config status and giving them a real directive — this module
should need no changes for that.
"""

from __future__ import annotations

import re
from datetime import date

from brain.config import BrainConfig
from brain.hq import HQ
from brain.llm import LLM
from brain.models import EscalationItem
from brain.tools import TOOL_SCHEMAS, execute_tool

ESCALATION_BLOCK_RE = re.compile(
    r"^### ESCALATION\s*\n- Urgency:\s*(urgent|normal)\s*\n- Summary:\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_escalations(report: str) -> list[tuple[str, str]]:
    """[(urgency, summary)] from the report's ### ESCALATION blocks."""
    return [
        (m.group(1).lower(), m.group(2).strip())
        for m in ESCALATION_BLOCK_RE.finditer(report)
    ]


def run_agent(dept: str, config: BrainConfig, hq: HQ, llm: LLM,
              print_fn=print) -> int:
    """Execute one scheduled run for a department. Returns an exit code
    (0 = ok / nothing to do, 1 = misconfigured)."""
    dept_config = config.departments.get(dept)
    if dept_config is None:
        print_fn(f"Unknown department {dept!r}. Registered: {', '.join(config.departments)}")
        return 1
    if dept_config.status != "active":
        # Kill switch semantics: dormant/suspended runs exit immediately.
        print_fn(f"{dept} is {dept_config.status} — agent run skipped.")
        return 0

    week = hq.current_week_key()
    directive = hq.read_directive(dept)
    last_week = hq.latest_report_week(dept)
    last_report = hq.read_report(dept, last_week) if last_week and last_week != week else None

    static = "\n\n---\n\n".join([
        (config.prompts_root / "agent_core.md").read_text(encoding="utf-8"),
        hq.read_company_charter(),
        hq.read_tiers(),
    ])
    dynamic_parts = [f"### Your standing directive\n\n{directive}"]
    if last_report:
        dynamic_parts.append(f"### Your previous report ({last_week})\n\n{last_report}")
    else:
        dynamic_parts.append("### Your previous report\n\nNone — this is your first report.")
    system_blocks = [
        {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "\n\n".join(dynamic_parts)},
    ]

    print_fn(f"[{dept}] researching (week {week})...")
    report = llm.call_with_web_search(
        system_blocks,
        f"Today is {date.today().isoformat()}, week {week}. Research per your "
        f"standing directive and produce this week's report.",
        max_tokens=config.max_tokens["agent"],
        max_searches=config.agent_max_searches,
        # Read-only live-check tools (domain/handle availability) — no
        # write/spend capability, so these bypass the executor and stay
        # inside Tier 0 for every department per the action-layer spec.
        extra_tools=TOOL_SCHEMAS,
        tool_executor=execute_tool,
    )

    report = report.strip() + "\n"
    path = hq.write_report(dept, week, report)
    print_fn(f"[{dept}] report written: {path}")

    escalations = parse_escalations(report)
    for urgency, summary in escalations:
        escalation_id = hq.append_escalation(EscalationItem(
            id="", raised=date.today(), raised_by=dept,
            urgency=urgency, summary=summary,
        ))
        print_fn(f"[{dept}] escalation filed: {escalation_id} ({urgency}) {summary}")
    if not escalations:
        print_fn(f"[{dept}] no escalations raised.")

    return 0
