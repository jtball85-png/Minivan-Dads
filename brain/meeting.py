"""The board meeting as a session object, shared by the CLI and the
dashboard (same pattern as BoardroomSession): load the agenda into items,
record rulings (with optional per-item sidebar discussion), then one
synthesis call writes minutes / decision-log entries / directive updates
(tier-ratification guarded) / escalation resolutions.

prepare_close/commit_close are split so the dashboard's tier-ratification
round-trip never re-runs the synthesis model or double-appends decisions —
identical contract to BoardroomSession.prepare_records/commit_records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from brain.config import BrainConfig
from brain.governance import DECISION_HEADING_RE
from brain.hq import HQ
from brain.interaction import Exchange, render_exchanges
from brain.llm import LLM
from brain.models import MeetingRuling
from brain.prompts import build_system_blocks
from brain.records import (
    RESOLVED_LINE_RE,
    extract_directive_updates,
    parse_decision_entries,
    split_sections,
    tier_or_status_changed,
)

MEETING_OUTPUT_SECTIONS = ["Minutes", "Decision Log Entries", "Directive Updates", "Resolved Escalations"]
# Split ONLY on the four known section headings — directive content inside
# the output legitimately contains its own ## headings (## Tier, ## Mandate)
# and must not break the split.
MEETING_SECTION_RE = re.compile(
    r"^## (Minutes|Decision Log Entries|Directive Updates|Resolved Escalations)\s*$", re.MULTILINE
)
TAG_IN_BLOCK_RE = re.compile(r"\[(BRAIN DECIDES|CEO REQUIRED)\]")


def render_rulings(rulings: list[MeetingRuling]) -> str:
    """Render rulings (with any sidebar discussion) for the synthesis call."""
    parts = []
    for r in rulings:
        line = f"- {r.item_title}: {r.action.upper()}"
        if r.ceo_note:
            line += f" — CEO note: {r.ceo_note}"
        if r.discussion:
            line += "\n  Discussion during ruling:\n" + render_exchanges(r.discussion, indent="    ")
        parts.append(line)
    return "\n".join(parts)


@dataclass
class AgendaItem:
    id: int
    title: str
    block_text: str
    tag: str  # "BRAIN DECIDES" | "CEO REQUIRED" | ""
    ruling: MeetingRuling | None = None
    discussion: list[Exchange] = field(default_factory=list)


class MeetingSession:
    def __init__(self, llm: LLM, config: BrainConfig, hq: HQ):
        self.llm = llm
        self.config = config
        self.hq = hq
        self.week = hq.current_week_key()
        self.agenda: str = ""
        self.items: list[AgendaItem] = []

    def load_agenda(self) -> list[AgendaItem]:
        agenda_path = self.hq.root / "meetings" / f"{self.week}-agenda.md"
        if not agenda_path.exists():
            raise FileNotFoundError(f"No agenda for {self.week}. Run `brain ingest` first.")
        self.agenda = agenda_path.read_text(encoding="utf-8")

        blocks = list(DECISION_HEADING_RE.finditer(self.agenda))
        self.items = []
        for i, m in enumerate(blocks):
            start = m.start()
            end = blocks[i + 1].start() if i + 1 < len(blocks) else len(self.agenda)
            block_text = self.agenda[start:end].strip()
            tag_m = TAG_IN_BLOCK_RE.search(block_text)
            self.items.append(AgendaItem(
                id=i,
                title=m.group(1).strip(),
                block_text=block_text,
                tag=tag_m.group(1) if tag_m else "",
            ))
        return self.items

    def _item(self, item_id: int) -> AgendaItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise ValueError(f"No agenda item {item_id}")

    def discuss(self, item_id: int, ceo_text: str) -> str:
        """Sidebar conversation about one item; recorded on that item."""
        from brain.main import make_discusser

        item = self._item(item_id)
        item.discussion.append(Exchange("CEO", ceo_text))
        reply = make_discusser(self.llm, self.config, self.hq, item.block_text)(
            ceo_text, item.discussion
        )
        item.discussion.append(Exchange("brain", reply))
        return reply

    def record_ruling(self, item_id: int, action: str, note: str = "") -> None:
        if action not in ("approve", "modify", "reject", "skip"):
            raise ValueError(f"Unknown ruling action {action!r}")
        item = self._item(item_id)
        item.ruling = MeetingRuling(
            item_title=item.title, action=action, ceo_note=note,
            discussion=item.discussion,
        )

    def rulings(self) -> list[MeetingRuling]:
        """Rulings in item order; unruled items count as skipped."""
        result = []
        for item in self.items:
            result.append(item.ruling or MeetingRuling(
                item_title=item.title, action="skip", discussion=item.discussion,
            ))
        return result

    # ------------------------------------------------------------------

    def render_rulings(self) -> str:
        return render_rulings(self.rulings())

    def prepare_close(self) -> dict:
        """The synthesis LLM call + parsing, NO writes."""
        user_message = (
            f"The {self.week} board meeting is over. Here is the agenda:\n\n{self.agenda}\n\n"
            f"---\n\nThe CEO's rulings:\n\n{self.render_rulings()}\n\n"
            f"Today's date is {date.today().isoformat()}. Produce the meeting records."
        )
        system_blocks = build_system_blocks(self.config, self.hq, "meeting_synthesis.md")
        output = self.llm.call(system_blocks, user_message,
                               max_tokens=self.config.max_tokens["meeting"])

        sections = split_sections(output, MEETING_SECTION_RE)
        missing = [s for s in MEETING_OUTPUT_SECTIONS if s not in sections]
        if missing:
            return {"raw_output": output, "missing_sections": missing}

        entries = parse_decision_entries(sections["Decision Log Entries"])
        updates, warnings = extract_directive_updates(
            sections["Directive Updates"], self.hq.list_departments()
        )
        pending_ratifications = []
        for dept, content in updates.items():
            try:
                current = self.hq.read_directive(dept)
            except FileNotFoundError:
                current = ""
            change = tier_or_status_changed(current, content) if current else None
            if change:
                pending_ratifications.append({"dept": dept, "change": change})

        return {
            "sections": sections,
            "entries": entries,
            "updates": updates,
            "warnings": warnings,
            "pending_ratifications": pending_ratifications,
            "missing_sections": [],
        }

    def commit_close(self, prepared: dict, ratify_fn=None) -> dict:
        """All HQ writes for a prepared close. `ratify_fn(dept, change) ->
        bool` gates tier/status changes; default declines (never silent)."""
        if prepared.get("missing_sections"):
            # Don't lose the meeting: raw output becomes the minutes.
            path = self.hq.write_minutes(self.week, prepared["raw_output"])
            return {
                "minutes_path": path,
                "decisions": 0, "directives_updated": [], "escalations_resolved": 0,
                "warnings": [
                    f"synthesis output missing sections {prepared['missing_sections']} — "
                    f"raw output saved as minutes; records NOT auto-applied, review manually"
                ],
            }

        sections = prepared["sections"]
        warnings = list(prepared["warnings"])
        pending = {p["dept"]: p["change"] for p in prepared["pending_ratifications"]}
        ratify = ratify_fn or (lambda dept, change: False)

        minutes_path = self.hq.write_minutes(
            self.week, f"# Board Meeting Minutes — {self.week}\n\n{sections['Minutes']}\n"
        )
        for entry in prepared["entries"]:
            self.hq.append_decision(entry)

        written = []
        for dept, content in prepared["updates"].items():
            change = pending.get(dept)
            if change and not ratify(dept, change):
                warnings.append(
                    f"directive update for {dept} included a tier/status change "
                    f"({change}) the CEO did not ratify — skipped"
                )
                continue
            self.hq.write_directive(dept, content)
            written.append(dept)

        resolved = 0
        for m in RESOLVED_LINE_RE.finditer(sections["Resolved Escalations"]):
            try:
                self.hq.resolve_escalation(m.group(1), resolution=m.group(2).strip(),
                                           decided_by="CEO")
                resolved += 1
            except ValueError as e:
                warnings.append(f"{e} — skipped")

        return {
            "minutes_path": minutes_path,
            "decisions": len(prepared["entries"]),
            "directives_updated": written,
            "escalations_resolved": resolved,
            "warnings": warnings,
        }

    def close(self, ratify_fn=None) -> dict:
        return self.commit_close(self.prepare_close(), ratify_fn)


def run_ingest(hq: HQ, llm: LLM, config: BrainConfig, print_fn=print) -> dict:
    """The ingest core (shared CLI/dashboard): discover reports, synthesize
    the agenda, run governance, write it."""
    from brain.governance import apply_governance

    week = hq.current_week_key()
    last_meeting = hq.last_meeting_date()
    since_week = hq.week_key_for_date(last_meeting) if last_meeting else "1970-W01"

    reports = hq.discover_reports(since_week)
    filed = {dept: entries for dept, entries in reports.items() if entries}
    print_fn(f"Reports found since {since_week}: "
             + (", ".join(f"{d} ({len(e)})" for d, e in filed.items()) if filed else "none"))

    system_blocks = build_system_blocks(config, hq, "ingest.md")
    trigger = (
        f"Prepare the board meeting agenda for {week}. "
        f"Reports discovered since the last meeting are already in your context."
    )
    raw_agenda = llm.call(system_blocks, trigger, max_tokens=config.max_tokens["ingest"])

    corrected_agenda, enforced = apply_governance(raw_agenda)
    upgrades = [e for e in enforced if e.upgraded]
    path = hq.write_agenda(week, corrected_agenda)

    return {
        "week": week,
        "path": path,
        "decisions": len(enforced),
        "upgrades": [{"title": e.title, "reasons": e.reasons} for e in upgrades],
        "reports_found": {d: len(e) for d, e in filed.items()},
    }
