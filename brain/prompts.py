"""Loads and assembles prompt files with full HQ context. Every
judgment-producing command loads, in this fixed order: charter -> tiers ->
all directives -> current+previous week reports -> last N decisions ->
open escalations -- before building the request. This is a hard rule from
the brief, not a suggestion."""

from __future__ import annotations

from datetime import date

from brain.config import BrainConfig
from brain.hq import HQ


def _read_prompt(config: BrainConfig, name: str) -> str:
    return (config.prompts_root / name).read_text(encoding="utf-8")


def build_static_system_text(config: BrainConfig, hq: HQ, command_prompt_file: str) -> str:
    parts = [
        _read_prompt(config, "system_core.md"),
        "# Charter\n\n" + hq.read_company_charter(),
        "# Authority Tiers\n\n" + hq.read_tiers(),
        "# Command Instructions\n\n" + _read_prompt(config, command_prompt_file),
    ]
    return "\n\n---\n\n".join(parts)


def build_dynamic_context_text(hq: HQ, as_of: date | None = None) -> str:
    sections: list[str] = ["# Current Directives"]
    for dept in hq.list_departments():
        try:
            content = hq.read_directive(dept)
        except FileNotFoundError:
            content = "(no directive on file)"
        sections.append(f"## Directive: {dept}\n\n{content}")

    current_week = hq.current_week_key(as_of=as_of)
    previous_week = hq.previous_week_key(as_of=as_of)
    sections.append("# Reports (current + previous week)")
    for dept in hq.list_departments():
        for week_key in (previous_week, current_week):
            report = hq.read_report(dept, week_key)
            if report is not None:
                sections.append(f"## Report: {dept} — {week_key}\n\n{report}")
            else:
                sections.append(f"## NO REPORT FILED: {dept} — {week_key}")

    sections.append(f"# Recent Decisions (last {hq.config.decision_log_recent_n})")
    decisions = hq.read_decisions(limit=hq.config.decision_log_recent_n)
    if decisions:
        for d in decisions:
            depts = ", ".join(d.departments) if d.departments else "none"
            sections.append(
                f"## {d.date.isoformat()} — {d.title}\n"
                f"- Rationale: {d.rationale}\n"
                f"- Decided by: {d.decided_by}\n"
                f"- Affected departments: {depts}"
            )
    else:
        sections.append("(no decisions logged yet)")

    sections.append("# Open Escalations")
    escalations = hq.read_escalation_queue()
    if escalations:
        for e in escalations:
            sections.append(
                f"## {e.id} ({e.urgency})\n"
                f"- Raised: {e.raised.isoformat()} by {e.raised_by}\n"
                f"- Summary: {e.summary}"
            )
    else:
        sections.append("(no open escalations)")

    return "\n\n".join(sections)


def build_system_blocks(
    config: BrainConfig, hq: HQ, command_prompt_file: str, as_of: date | None = None
) -> list[dict]:
    """Two-block system parameter: block 1 (system_core + charter + tiers +
    command instructions) is near-static across calls and marked for
    prompt caching; block 2 (directives/reports/decisions/escalations)
    changes weekly and is left uncached."""
    static_text = build_static_system_text(config, hq, command_prompt_file)
    dynamic_text = build_dynamic_context_text(hq, as_of=as_of)
    return [
        {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_text},
    ]
