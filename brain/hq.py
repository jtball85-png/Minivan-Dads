"""All HQ read/write operations live here. HQ is a plain Markdown +
directories file store — no database. This module is the only code
permitted to touch files under hq_root directly; everything else (main.py,
future department agents) goes through an HQ instance.

Kept import-light and dependency-free (stdlib only) so it can be imported
by future department-agent scripts per the brief's forward-compat
requirement.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from brain.actions.models import ActionRecord
from brain.config import BrainConfig
from brain.models import DecisionEntry, EscalationItem, LLMUsageRecord, ReportEntry, ReportStatus

WEEK_KEY_RE = re.compile(r"^(\d{4})-W(\d{2})$")
DECISION_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) — (.+)$", re.MULTILINE)
ESCALATION_HEADING_RE = re.compile(r"^## (ESC-\d+)\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^- ([A-Za-z][A-Za-z ]*?):\s*(.*)$", re.MULTILINE)
LAST_UPDATED_RE = re.compile(r"^Last updated:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
MINUTES_FILENAME_RE = re.compile(r"^(\d{4}-W\d{2})-minutes\.md$")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _parse_week_key(week_key: str) -> tuple[int, int]:
    m = WEEK_KEY_RE.match(week_key)
    if not m:
        raise ValueError(f"Invalid week key: {week_key!r}")
    return int(m.group(1)), int(m.group(2))


def _split_escalation_blocks(text: str) -> dict[str, tuple[int, int, str]]:
    """Returns {id: (start, end, block_text)} for each '## ESC-N' block,
    where block_text spans from the heading through (not including) the
    next heading or EOF."""
    matches = list(ESCALATION_HEADING_RE.finditer(text))
    blocks: dict[str, tuple[int, int, str]] = {}
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[m.group(1)] = (start, end, text[start:end])
    return blocks


def _parse_fields(block: str) -> dict[str, str]:
    return {
        m.group(1).strip().lower().replace(" ", "_"): m.group(2).strip()
        for m in FIELD_RE.finditer(block)
    }


def _escalation_from_block(escalation_id: str, block: str) -> EscalationItem:
    fields = _parse_fields(block)
    return EscalationItem(
        id=escalation_id,
        raised=date.fromisoformat(fields["raised"]),
        raised_by=fields.get("raised_by", ""),
        urgency=fields.get("urgency", "normal"),
        summary=fields.get("summary", ""),
        resolved=date.fromisoformat(fields["resolved"]) if "resolved" in fields else None,
        resolution=fields.get("resolution"),
        decided_by=fields.get("decided_by"),
    )


class HQ:
    def __init__(self, config: BrainConfig):
        self.config = config
        self.root = config.hq_root

    # ---- Charter ----------------------------------------------------

    def read_company_charter(self) -> str:
        return (self.root / "charter" / "company.md").read_text(encoding="utf-8")

    def read_tiers(self) -> str:
        return (self.root / "charter" / "tiers.md").read_text(encoding="utf-8")

    def read_roadmap(self) -> str:
        return (self.root / "charter" / "roadmap.md").read_text(encoding="utf-8")

    # ---- Directives ---------------------------------------------------

    def list_departments(self) -> list[str]:
        return self.config.department_names()

    def _directive_path(self, dept: str) -> Path:
        return self.root / "directives" / f"{dept}.md"

    def read_directive(self, dept: str) -> str:
        path = self._directive_path(dept)
        if not path.exists():
            raise FileNotFoundError(f"No directive file for department: {dept}")
        return path.read_text(encoding="utf-8")

    def write_directive(self, dept: str, content: str) -> Path:
        path = self._directive_path(dept)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def directive_updated_at(self, dept: str) -> date | None:
        path = self._directive_path(dept)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        m = LAST_UPDATED_RE.search(text)
        if m:
            return date.fromisoformat(m.group(1))
        return date.fromtimestamp(path.stat().st_mtime)

    def stale_directives(self, days: int = 30, as_of: date | None = None) -> list[str]:
        as_of = as_of or date.today()
        stale = []
        for dept in self.list_departments():
            updated = self.directive_updated_at(dept)
            if updated is not None and (as_of - updated).days > days:
                stale.append(dept)
        return stale

    # ---- Reports --------------------------------------------------------

    def week_key_for_date(self, d: date) -> str:
        year, week, _ = d.isocalendar()
        return f"{year}-W{week:02d}"

    def current_week_key(self, as_of: date | None = None) -> str:
        return self.week_key_for_date(as_of or date.today())

    def previous_week_key(self, as_of: date | None = None) -> str:
        as_of = as_of or date.today()
        return self.week_key_for_date(as_of - timedelta(days=7))

    def _reports_dir(self, dept: str) -> Path:
        return self.root / "reports" / dept

    def report_path(self, dept: str, week_key: str) -> Path:
        return self._reports_dir(dept) / f"{week_key}.md"

    def read_report(self, dept: str, week_key: str) -> str | None:
        path = self.report_path(dept, week_key)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_report(self, dept: str, week_key: str, content: str) -> Path:
        path = self.report_path(dept, week_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def latest_report_week(self, dept: str) -> str | None:
        """Newest week-keyed report filename for a department, or None."""
        reports_dir = self._reports_dir(dept)
        if not reports_dir.exists():
            return None
        weeks = [p.stem for p in reports_dir.glob("*.md") if WEEK_KEY_RE.match(p.stem)]
        return max(weeks, key=_parse_week_key) if weeks else None

    def reports_status(self, week_key: str | None = None) -> dict[str, ReportStatus]:
        week_key = week_key or self.current_week_key()
        status: dict[str, ReportStatus] = {}
        for dept, dept_config in self.config.departments.items():
            if dept_config.status == "dormant":
                status[dept] = ReportStatus.DORMANT
            elif self.report_path(dept, week_key).exists():
                status[dept] = ReportStatus.FILED
            else:
                status[dept] = ReportStatus.MISSING
        return status

    def discover_reports(self, since_week_key: str) -> dict[str, list[ReportEntry]]:
        cutoff = _parse_week_key(since_week_key)
        result: dict[str, list[ReportEntry]] = {}
        for dept in self.list_departments():
            reports_dir = self._reports_dir(dept)
            entries: list[ReportEntry] = []
            if reports_dir.exists():
                for path in reports_dir.glob("*.md"):
                    week_key = path.stem
                    if not WEEK_KEY_RE.match(week_key):
                        continue
                    if _parse_week_key(week_key) >= cutoff:
                        entries.append(
                            ReportEntry(
                                department=dept,
                                week_key=week_key,
                                content=path.read_text(encoding="utf-8"),
                            )
                        )
            entries.sort(key=lambda e: _parse_week_key(e.week_key))
            result[dept] = entries
        return result

    # ---- Product catalog (snapshot of live products across platforms) ----

    def _product_catalog_path(self) -> Path:
        return self.root / "products" / "catalog.json"

    def read_product_catalog(self) -> dict:
        """The last-synced product snapshot, or an empty catalog if never
        synced. Read-only, no API call — the dashboard and agents read this
        file; refreshing it (the live pull) is an explicit sync."""
        path = self._product_catalog_path()
        if not path.exists():
            return {"generated_at": None, "products": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def write_product_catalog(self, generated_at: str, products: list[dict]) -> Path:
        """Persist the unified catalog: machine-readable JSON + a human-readable
        Markdown mirror the CEO can read straight from git."""
        path = self._product_catalog_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        catalog = {"generated_at": generated_at, "products": products}
        _atomic_write(path, json.dumps(catalog, indent=2) + "\n")
        _atomic_write(path.with_suffix(".md"), self._product_catalog_md(catalog))
        return path

    def product_catalog_markdown(self) -> str:
        """The current catalog as the human/agent-readable Markdown string."""
        return self._product_catalog_md(self.read_product_catalog())

    @staticmethod
    def _product_catalog_md(catalog: dict) -> str:
        lines = ["# Product catalog",
                 f"\n_Last synced: {catalog.get('generated_at') or 'never'}_\n"]
        products = catalog.get("products", [])
        if not products:
            lines.append("\nNo products synced yet.\n")
            return "\n".join(lines)
        for p in products:
            lines.append(f"\n## {p.get('title', '(untitled)')}  ·  {p.get('platform')}")
            lines.append(f"- Status: {p.get('status')}")
            lines.append(f"- External id: {p.get('external_id') or '—'}")
            lines.append(f"- Colorways: {', '.join(p.get('colorways', [])) or '—'}")
            lines.append(f"- Sizes: {', '.join(p.get('sizes', [])) or '—'}")
            lines.append(f"- Price: {p.get('price_range', 'not set')}")
        return "\n".join(lines) + "\n"

    # ---- Decisions (append-only) -----------------------------------------

    def _decisions_log_path(self) -> Path:
        return self.root / "decisions" / "log.md"

    def append_decision(self, entry: DecisionEntry) -> None:
        path = self._decisions_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        departments = ", ".join(entry.departments) if entry.departments else "none"
        block = (
            f"\n## {entry.date.isoformat()} — {entry.title}\n"
            f"- Rationale: {entry.rationale}\n"
            f"- Decided by: {entry.decided_by}\n"
            f"- Affected departments: {departments}\n"
        )
        if not path.exists():
            header = "# Decision Log\n\nAppend-only.\n"
            path.write_text(header, encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)

    def read_decisions(self, limit: int = 20) -> list[DecisionEntry]:
        path = self._decisions_log_path()
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        headings = list(DECISION_HEADING_RE.finditer(text))
        entries: list[DecisionEntry] = []
        for i, m in enumerate(headings):
            start = m.start()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            block = text[start:end]
            fields = _parse_fields(block)
            departments_raw = fields.get("affected_departments", "")
            departments = (
                [d.strip() for d in departments_raw.split(",") if d.strip() and d.strip() != "none"]
                if departments_raw
                else []
            )
            entries.append(
                DecisionEntry(
                    date=date.fromisoformat(m.group(1)),
                    title=m.group(2).strip(),
                    rationale=fields.get("rationale", ""),
                    decided_by=fields.get("decided_by", ""),
                    departments=departments,
                )
            )
        return entries[-limit:] if limit else entries

    # ---- Escalations --------------------------------------------------

    def _queue_path(self) -> Path:
        return self.root / "escalations" / "queue.md"

    def _resolved_path(self) -> Path:
        return self.root / "escalations" / "resolved.md"

    def read_escalation_queue(self) -> list[EscalationItem]:
        path = self._queue_path()
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        blocks = _split_escalation_blocks(text)
        items = [_escalation_from_block(eid, block) for eid, (_, _, block) in blocks.items()]
        items.sort(key=lambda item: 0 if item.urgency == "urgent" else 1)
        return items

    def read_resolved_escalations(self) -> list[EscalationItem]:
        path = self._resolved_path()
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        blocks = _split_escalation_blocks(text)
        return [_escalation_from_block(eid, block) for eid, (_, _, block) in blocks.items()]

    def next_escalation_id(self) -> str:
        max_n = 0
        for path in (self._queue_path(), self._resolved_path()):
            if not path.exists():
                continue
            for m in ESCALATION_HEADING_RE.finditer(path.read_text(encoding="utf-8")):
                n = int(m.group(1).split("-")[1])
                max_n = max(max_n, n)
        return f"ESC-{max_n + 1:03d}"

    def append_escalation(self, item: EscalationItem) -> str:
        escalation_id = item.id or self.next_escalation_id()
        path = self._queue_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        block = (
            f"\n## {escalation_id}\n"
            f"- Raised: {item.raised.isoformat()}\n"
            f"- Raised by: {item.raised_by}\n"
            f"- Urgency: {item.urgency}\n"
            f"- Summary: {item.summary}\n"
        )
        if not path.exists():
            path.write_text("# Escalation Queue\n\n", encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
        return escalation_id

    def resolve_escalation(
        self,
        escalation_id: str,
        resolution: str,
        decided_by: str,
        as_of: date | None = None,
    ) -> None:
        as_of = as_of or date.today()
        queue_path = self._queue_path()
        if not queue_path.exists():
            raise ValueError(f"No escalation queue found; cannot resolve {escalation_id}")

        text = queue_path.read_text(encoding="utf-8")
        blocks = _split_escalation_blocks(text)
        if escalation_id not in blocks:
            raise ValueError(f"Escalation {escalation_id} not found in queue")

        start, end, block = blocks[escalation_id]
        new_queue_text = text[:start] + text[end:]

        # Rewrite the queue atomically first — if this fails, nothing else
        # has been touched and queue.md is left exactly as it was.
        _atomic_write(queue_path, new_queue_text)

        item = _escalation_from_block(escalation_id, block)
        item = replace(item, resolved=as_of, resolution=resolution, decided_by=decided_by)

        resolved_path = self._resolved_path()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_block = (
            f"\n## {item.id}\n"
            f"- Raised: {item.raised.isoformat()}\n"
            f"- Raised by: {item.raised_by}\n"
            f"- Urgency: {item.urgency}\n"
            f"- Summary: {item.summary}\n"
            f"- Resolved: {item.resolved.isoformat()}\n"
            f"- Resolution: {item.resolution}\n"
            f"- Decided by: {item.decided_by}\n"
        )
        if not resolved_path.exists():
            resolved_path.write_text("# Resolved Escalations\n\n", encoding="utf-8")
        with open(resolved_path, "a", encoding="utf-8") as f:
            f.write(resolved_block)

    # ---- Meetings -------------------------------------------------------

    def _meetings_dir(self) -> Path:
        return self.root / "meetings"

    def write_agenda(self, week_key: str, content: str) -> Path:
        path = self._meetings_dir() / f"{week_key}-agenda.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_minutes(self, week_key: str, content: str) -> Path:
        """Second meeting in the same week gets -2, -3... — minutes are a
        record; records don't get overwritten."""
        meetings_dir = self._meetings_dir()
        meetings_dir.mkdir(parents=True, exist_ok=True)
        path = meetings_dir / f"{week_key}-minutes.md"
        n = 2
        while path.exists():
            path = meetings_dir / f"{week_key}-minutes-{n}.md"
            n += 1
        path.write_text(content, encoding="utf-8")
        return path

    def write_boardroom_transcript(self, week_key: str, slug: str, content: str) -> Path:
        """hq/meetings/{week}-boardroom-{slug}.md; suffixes -2, -3... on
        collision so a second debate on the same topic never overwrites."""
        meetings_dir = self._meetings_dir()
        meetings_dir.mkdir(parents=True, exist_ok=True)
        base = f"{week_key}-boardroom-{slug}"
        path = meetings_dir / f"{base}.md"
        n = 2
        while path.exists():
            path = meetings_dir / f"{base}-{n}.md"
            n += 1
        path.write_text(content, encoding="utf-8")
        return path

    def write_collaboration(self, week_key: str, slug: str, content: str) -> Path:
        """hq/collaborations/{week}-{slug}.md — a joint department work-product.
        Collision-suffixed like transcripts so a repeat never overwrites."""
        collab_dir = self.root / "collaborations"
        collab_dir.mkdir(parents=True, exist_ok=True)
        base = f"{week_key}-{slug}"
        path = collab_dir / f"{base}.md"
        n = 2
        while path.exists():
            path = collab_dir / f"{base}-{n}.md"
            n += 1
        path.write_text(content, encoding="utf-8")
        return path

    def write_monthly_review(self, year_month: str, content: str) -> Path:
        path = self._meetings_dir() / "monthly" / f"{year_month}-review.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def research_exhibit_path(self, slug: str) -> Path:
        return self.root / "research" / f"{slug}.md"

    def write_research_exhibit(self, slug: str, content: str) -> Path:
        """Promote a garage research finding into HQ so a department agent
        can actually read it (see CLAUDE.md's 'Two rooms' section — this is
        the garage-to-board handoff point)."""
        path = self.research_exhibit_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_research_exhibit(self, slug: str) -> str:
        return self.research_exhibit_path(slug).read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Action log + snapshots (action layer)
    # ------------------------------------------------------------------

    def actions_log_path(self) -> Path:
        return self.root / "actions" / "log.jsonl"

    def append_action(self, record: ActionRecord) -> None:
        """Append one JSONL line. Like the decision log, this file is
        append-only: 'a' mode is the only mode ever used on it."""

        path = self.actions_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record.to_json_dict()) + "\n")

    def read_actions(self, since: date | None = None) -> list[ActionRecord]:
        """Current state per action id: lines are grouped by id and the last
        line wins (an action's lifecycle is multiple appended lines). Returns
        records in first-seen id order, filtered by `since` (timestamp date)."""

        path = self.actions_log_path()
        if not path.exists():
            return []

        latest: dict[str, ActionRecord] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = ActionRecord.from_json_dict(json.loads(line))
            latest[record.id] = record  # dict preserves first-seen order; value updates

        records = list(latest.values())
        if since is not None:
            records = [r for r in records if date.fromisoformat(r.timestamp[:10]) >= since]
        return records

    def llm_usage_log_path(self) -> Path:
        return self.root / "actions" / "llm_usage.jsonl"

    def append_llm_usage(self, record: LLMUsageRecord) -> None:
        """Append one JSONL line — cost telemetry, not a company decision,
        but still append-only ('a' mode only) so nothing silently drops
        from the CEO's view of spend."""
        path = self.llm_usage_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record.to_json_dict()) + "\n")

    def read_llm_usage(self, since: date | None = None) -> list[LLMUsageRecord]:
        path = self.llm_usage_log_path()
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(LLMUsageRecord.from_json_dict(json.loads(line)))
        if since is not None:
            records = [r for r in records if date.fromisoformat(r.timestamp[:10]) >= since]
        return records

    def snapshot_path(self, action_id: str) -> Path:
        return self.root / "actions" / "snapshots" / f"{action_id}.json"

    def write_snapshot(self, action_id: str, data: dict) -> Path:

        path = self.snapshot_path(action_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps(data, indent=2))
        return path

    def read_snapshot(self, action_id: str) -> dict:

        return json.loads(self.snapshot_path(action_id).read_text(encoding="utf-8"))

    def next_action_id(self, as_of: date | None = None) -> str:
        week = self.current_week_key(as_of)
        existing = [r.id for r in self.read_actions() if r.id.startswith(f"ACT-{week}-")]
        seq = 1
        if existing:
            seq = max(int(i.rsplit("-", 1)[1]) for i in existing) + 1
        return f"ACT-{week}-{seq:04d}"

    def action_stats(self, days: int = 7, as_of: date | None = None) -> dict[str, dict[str, int]]:
        """Per-agent counts of final states within the window — the status
        dashboard's Actions section."""
        cutoff = (as_of or date.today()) - timedelta(days=days)
        stats: dict[str, dict[str, int]] = {}
        for record in self.read_actions(since=cutoff):
            agent_stats = stats.setdefault(record.agent, {})
            agent_stats[record.result] = agent_stats.get(record.result, 0) + 1
        return stats

    def last_meeting_date(self) -> date | None:
        meetings_dir = self._meetings_dir()
        if not meetings_dir.exists():
            return None
        dates: list[date] = []
        for path in meetings_dir.glob("*-minutes.md"):
            m = MINUTES_FILENAME_RE.match(path.name)
            if not m:
                continue
            year, week = _parse_week_key(m.group(1))
            dates.append(date.fromisocalendar(year, week, 1))
        return max(dates) if dates else None
