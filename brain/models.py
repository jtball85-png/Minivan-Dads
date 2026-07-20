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
class LLMUsageRecord:
    """One line in hq/actions/llm_usage.jsonl. Append-only cost telemetry —
    one record per underlying API call, tagged with the command that made
    it, so the CEO can see both weekly burn and typical cost per action."""

    timestamp: str          # ISO 8601
    command: str            # e.g. "ask", "ingest", "meeting", "agent:market_intel"
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def to_json_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "command": self.command,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
        }

    @classmethod
    def from_json_dict(cls, d: dict) -> "LLMUsageRecord":
        return cls(
            timestamp=d["timestamp"],
            command=d["command"],
            model=d["model"],
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            cache_creation_input_tokens=d.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=d.get("cache_read_input_tokens", 0),
        )


@dataclass
class MeetingRuling:
    item_title: str
    action: str  # "approve" | "modify" | "reject" | "skip"
    ceo_note: str = ""
    # Sidebar conversation held while ruling on this item (interaction.Exchange
    # objects; typed loosely here to keep models.py dependency-free).
    discussion: list = field(default_factory=list)
