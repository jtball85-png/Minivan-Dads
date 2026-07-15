"""Enforces the hard rule from the brief: spending money, brand-identity
changes, legal commitments, and irreversible actions are ALWAYS
[CEO REQUIRED], never [BRAIN DECIDES] — enforced in code, not just prompted
behavior.

Two independent, defense-in-depth mechanisms run as a post-processing pass
over LLM-generated markdown (never trusted from the prompt alone). A tag can
only ever be force-*upgraded* to CEO REQUIRED, never force-downgraded.

Expected decision block shape (produced by ingest.md / directive.md):

    #### Decision: <one-line title>
    - Recommendation: <text>
    - Checklist: money=no, brand=no, legal=no, irreversible=no
    - Tag: [BRAIN DECIDES]

(or `Tag: [CEO REQUIRED]` with an added `- Reason: <text>` line).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DECISION_HEADING_RE = re.compile(r"^#### Decision: (.+)$", re.MULTILINE)
TAG_LINE_RE = re.compile(r"^- Tag:\s*\[(BRAIN DECIDES|CEO REQUIRED)\]\s*$", re.MULTILINE)
CHECKLIST_LINE_RE = re.compile(r"^- Checklist:\s*(.+)$", re.MULTILINE)
RECOMMENDATION_LINE_RE = re.compile(r"^- Recommendation:\s*(.*)$", re.MULTILINE)
REASON_LINE_RE = re.compile(r"^- Reason:.*$", re.MULTILINE)

CEO_REQUIRED = "CEO REQUIRED"
BRAIN_DECIDES = "BRAIN DECIDES"

FORCE_CEO_KEYWORDS: dict[str, list[str]] = {
    "spend": [r"\bspend\b", r"\bspending\b", r"\bbudget\b", r"\bpurchase\b", r"\binvoice\b",
              r"\bad spend\b", r"\$\d", r"\bprice increase\b", r"\bpayment\b"],
    "brand": [r"\brebrand\b", r"\bnew logo\b", r"\brename\b", r"\btagline\b",
              r"\bbrand name\b", r"\bbrand voice\b", r"\blogo change\b"],
    "legal": [r"\btrademark\b", r"\bcontract\b", r"\blegal\b", r"\bcopyright\b",
              r"\bterms of service\b", r"\blawsuit\b", r"\bcease and desist\b"],
    "irreversible": [r"\bdelete\b", r"\bpermanently\b", r"\bterminate\b",
                      r"\bclose the shop\b", r"\bcancel\b.*\baccount\b", r"\birreversible\b"],
}


@dataclass
class ParsedDecision:
    title: str
    block_text: str
    recommendation: str = ""
    checklist: dict[str, bool] = field(default_factory=dict)
    tag: str | None = None
    well_formed: bool = False


@dataclass
class EnforcedDecision:
    title: str
    final_tag: str
    upgraded: bool
    reasons: list[str] = field(default_factory=list)


def _split_decision_blocks(markdown: str) -> list[tuple[int, int, str]]:
    """Returns [(start, end, block_text)] for each '#### Decision:' block."""
    matches = list(DECISION_HEADING_RE.finditer(markdown))
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        blocks.append((start, end, markdown[start:end]))
    return blocks


def _parse_checklist(checklist_line: str) -> dict[str, bool]:
    result = {}
    for pair in checklist_line.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        result[key.strip().lower()] = value.strip().lower() == "yes"
    return result


def parse_decision_blocks(markdown: str) -> list[ParsedDecision]:
    decisions = []
    for _, _, block_text in _split_decision_blocks(markdown):
        heading_m = DECISION_HEADING_RE.search(block_text)
        title = heading_m.group(1).strip() if heading_m else ""

        tag_m = TAG_LINE_RE.search(block_text)
        checklist_m = CHECKLIST_LINE_RE.search(block_text)
        recommendation_m = RECOMMENDATION_LINE_RE.search(block_text)

        tag = tag_m.group(1) if tag_m else None
        checklist = _parse_checklist(checklist_m.group(1)) if checklist_m else {}
        recommendation = recommendation_m.group(1).strip() if recommendation_m else ""
        expected_keys = {"money", "brand", "legal", "irreversible"}
        well_formed = tag is not None and checklist_m is not None and expected_keys.issubset(checklist.keys())

        decisions.append(
            ParsedDecision(
                title=title,
                block_text=block_text,
                recommendation=recommendation,
                checklist=checklist,
                tag=tag,
                well_formed=well_formed,
            )
        )
    return decisions


def classify_forced_categories(text: str) -> set[str]:
    """Independent keyword backstop — runs regardless of what the checklist
    says, to catch cases where the model mis-answers its own checklist."""
    hits = set()
    lowered = text.lower()
    for category, patterns in FORCE_CEO_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                hits.add(category)
                break
    return hits


def enforce_tier(decision: ParsedDecision) -> EnforcedDecision:
    if not decision.well_formed:
        return EnforcedDecision(
            title=decision.title,
            final_tag=CEO_REQUIRED,
            upgraded=True,
            reasons=["malformed or missing checklist/tag (fail-safe default)"],
        )

    reasons: list[str] = []

    checklist_hits = [k for k, v in decision.checklist.items() if v]
    if checklist_hits:
        reasons.append(f"checklist flagged: {', '.join(sorted(checklist_hits))}")

    # Scan only title + recommendation text, not the whole block — the
    # checklist/tag lines themselves contain words like "legal" and
    # "brand" as field names, which would otherwise self-trigger.
    keyword_hits = classify_forced_categories(f"{decision.title} {decision.recommendation}")
    if keyword_hits:
        reasons.append(f"keyword match on category: {', '.join(sorted(keyword_hits))}")

    if reasons:
        return EnforcedDecision(
            title=decision.title,
            final_tag=CEO_REQUIRED,
            upgraded=(decision.tag != CEO_REQUIRED),
            reasons=reasons,
        )

    return EnforcedDecision(
        title=decision.title,
        final_tag=decision.tag,
        upgraded=False,
        reasons=[],
    )


def _apply_correction(block_text: str, enforced: EnforcedDecision) -> str:
    if not enforced.upgraded:
        return block_text

    note = f"[auto-upgraded: {'; '.join(enforced.reasons)}]"

    if TAG_LINE_RE.search(block_text):
        new_text = TAG_LINE_RE.sub(f"- Tag: [{enforced.final_tag}]", block_text, count=1)
    else:
        new_text = block_text.rstrip("\n") + f"\n- Tag: [{enforced.final_tag}]"

    if REASON_LINE_RE.search(new_text):
        new_text = REASON_LINE_RE.sub(f"- Reason: {note}", new_text, count=1)
    else:
        new_text = new_text.rstrip("\n") + f"\n- Reason: {note}\n"

    return new_text


def apply_governance(markdown: str) -> tuple[str, list[EnforcedDecision]]:
    """Runs every decision block in markdown through enforce_tier() and
    returns the corrected markdown (governance-checked, safe to write to
    HQ) plus the list of enforcement results for logging/summary output."""
    blocks = _split_decision_blocks(markdown)
    enforced_results: list[EnforcedDecision] = []

    corrected = markdown
    # Apply corrections back-to-front so earlier offsets stay valid.
    for start, end, block_text in reversed(blocks):
        parsed = parse_decision_blocks(block_text)[0] if DECISION_HEADING_RE.search(block_text) else None
        if parsed is None:
            continue
        enforced = enforce_tier(parsed)
        enforced_results.insert(0, enforced)
        corrected_block = _apply_correction(block_text, enforced)
        corrected = corrected[:start] + corrected_block + corrected[end:]

    return corrected, enforced_results
