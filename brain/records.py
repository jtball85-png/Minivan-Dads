"""Shared machinery for parsing LLM-produced meeting/boardroom records into
HQ writes: fixed-heading section splitting, fenced directive extraction, and
decision-entry field parsing. Used by both `brain meeting` and
`brain boardroom` so there is exactly one implementation of each contract."""

from __future__ import annotations

import re
from datetime import date

from brain.models import DecisionEntry

LOG_ENTRY_HEADING_RE = re.compile(r"^### (.+)$", re.MULTILINE)
RESOLVED_LINE_RE = re.compile(r"^(ESC-\d+):\s*(.+)$", re.MULTILINE)
FENCED_BLOCK_RE = re.compile(r"```(?:markdown|md)?\s*\n(.*?)```", re.DOTALL)
FIELD_LINE_RE = re.compile(r"^- ([A-Za-z ]+):\s*(.+)$", re.MULTILINE)
TIER_RE = re.compile(r"\btier\s*:?\s*(?:\*\*)?\s*tier\s+([0-3])\b|^##\s*Tier\s*\n+\s*Tier\s+([0-3])\b",
                     re.IGNORECASE | re.MULTILINE)
STATUS_RE = re.compile(r"\bstatus\s*:?\s*(?:\*\*)?\s*(active|dormant|suspended)\b|^##\s*Status\s*\n+\s*(active|dormant|suspended)\b",
                       re.IGNORECASE | re.MULTILINE)


def _extract_tier_status(directive_text: str) -> tuple[str | None, str | None]:
    tier_m = TIER_RE.search(directive_text)
    status_m = STATUS_RE.search(directive_text)
    tier = (tier_m.group(1) or tier_m.group(2)) if tier_m else None
    status = ((status_m.group(1) or status_m.group(2)) or "").lower() if status_m else None
    return tier, status


def tier_or_status_changed(current: str, proposed: str) -> str | None:
    """Detect a tier or status change smuggled into a directive rewrite.
    Tier promotions/demotions and activations are EXPLICIT board decisions
    (roadmap standing rule: 'earned in the decision log, never assumed') —
    a synthesis model inferring one from a ruling is the failure mode this
    guards. Returns a human-readable description of the change, or None."""
    cur_tier, cur_status = _extract_tier_status(current)
    new_tier, new_status = _extract_tier_status(proposed)
    changes = []
    if cur_tier is not None and new_tier is not None and cur_tier != new_tier:
        changes.append(f"tier {cur_tier} -> {new_tier}")
    if cur_status is not None and new_status is not None and cur_status != new_status:
        changes.append(f"status {cur_status} -> {new_status}")
    return ", ".join(changes) if changes else None


def split_sections(markdown: str, heading_re: re.Pattern) -> dict[str, str]:
    """Split markdown into {heading: body} on a heading regex. The regex must
    capture the heading text in group 1 and should list only the KNOWN
    section names — LLM-written bodies legitimately contain their own ##
    headings (## Tier, ## Mandate) that must not break the split."""
    matches = list(heading_re.finditer(markdown))
    sections = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections[m.group(1).strip()] = markdown[start:end].strip()
    return sections


def parse_decision_entries(section_body: str, as_of: date | None = None) -> list[DecisionEntry]:
    """Parse a '## Decision Log Entries' section: one `### <title>` block per
    entry with `- Rationale / - Decided by / - Affected departments` fields."""
    entries = []
    for title, body in split_sections(section_body, LOG_ENTRY_HEADING_RE).items():
        fields = dict(FIELD_LINE_RE.findall(body))
        departments_raw = fields.get("Affected departments", "")
        departments = [
            d.strip() for d in departments_raw.split(",")
            if d.strip() and d.strip().lower() != "none"
        ]
        entries.append(
            DecisionEntry(
                date=as_of or date.today(),
                title=title,
                rationale=fields.get("Rationale", ""),
                decided_by=fields.get("Decided by", "CEO"),
                departments=departments,
            )
        )
    return entries


def extract_directive_updates(section_body: str,
                              known_departments: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse a '## Directive Updates' section: one `### <department>` block
    per changed directive, full replacement content inside a fenced code
    block. Returns ({department: new_content}, [warnings])."""
    updates: dict[str, str] = {}
    warnings: list[str] = []

    if section_body.strip() == "None.":
        return updates, warnings

    for dept, content in split_sections(section_body, LOG_ENTRY_HEADING_RE).items():
        # Models occasionally copy the template placeholder braces literally
        # ("### {market_intel}") — normalize before matching.
        dept_key = dept.strip().strip("{}").strip()
        if dept_key not in known_departments:
            warnings.append(f"unknown department {dept_key!r} in directive updates — skipped")
            continue
        fence_m = FENCED_BLOCK_RE.search(content)
        if not fence_m:
            warnings.append(
                f"directive update for {dept_key} was not in a fenced block — skipped, review manually"
            )
            continue
        updates[dept_key] = fence_m.group(1).strip() + "\n"
    return updates, warnings
