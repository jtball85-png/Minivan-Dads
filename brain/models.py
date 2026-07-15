"""Dataclasses for structured HQ records. hq.py reads/writes these; nothing
outside hq.py should construct them directly except when appending new
records via hq.py's own methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ReportStatus(str, Enum):
    FILED = "filed"
    MISSING = "missing"
    DORMANT = "dormant"


@dataclass
class ReportEntry:
    department: str
    week_key: str
    content: str


@dataclass
class DecisionEntry:
    date: date
    title: str
    rationale: str
    decided_by: str
    departments: list[str] = field(default_factory=list)


@dataclass
class EscalationItem:
    id: str
    raised: date
    raised_by: str
    urgency: str  # "urgent" | "normal"
    summary: str
    resolved: date | None = None
    resolution: str | None = None
    decided_by: str | None = None


@dataclass
class DepartmentConfig:
    name: str
    tier: int
    status: str  # "active" | "dormant"
    report_cadence: str


@dataclass
class MeetingRuling:
    item_title: str
    action: str  # "approve" | "modify" | "reject" | "skip"
    ceo_note: str = ""
