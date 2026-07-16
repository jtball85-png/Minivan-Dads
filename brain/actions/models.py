"""Data shapes for the action layer. Stdlib-only (like brain/models.py) so
hq.py can import ActionRecord without pulling in yaml or the executor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ActionMode(str, Enum):
    DRY_RUN = "dry_run"
    SUPERVISED = "supervised"
    AUTO = "auto"


# Ladder order for promotions/demotions (index = rung).
MODE_LADDER = [ActionMode.DRY_RUN, ActionMode.SUPERVISED, ActionMode.AUTO]


class ActionResult(str, Enum):
    DRY_RUN = "dry_run"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class ActionType:
    """A registered, possible write. Unregistered action = impossible action.
    Adding one is a code change reviewed by the CEO."""

    name: str                              # "shopify.update_listing_copy"
    connector: str                         # "shopify"
    params: dict[str, str]                 # param name -> "str" | "int" | "float" | "list"
    snapshot_params: tuple[str, ...] = ()  # params identifying the state to snapshot
    irreversible: bool = False             # no rollback; needs one rung higher to run live
    always_escalate: bool = False          # hardcoded global denial — never executes


@dataclass
class ActionIntent:
    """What an agent proposes. The executor decides what actually happens."""

    agent: str
    action_type: str
    params: dict
    rationale: str                 # carried to the escalation queue on rejection
    directive_version: str = ""    # "Last updated" date of the authorizing directive


@dataclass
class ActionRecord:
    """One line in hq/actions/log.jsonl. The log is append-only; an action's
    lifecycle is multiple lines sharing an id — the last line wins."""

    id: str                        # "ACT-2026-W29-0001"
    timestamp: str                 # ISO 8601
    agent: str
    action_type: str
    params: dict
    mode: str                      # ActionMode value
    result: str                    # ActionResult value
    snapshot_ref: str | None = None
    reasons: list[str] = field(default_factory=list)
    rollback_of: str | None = None
    directive_version: str = ""

    def to_json_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "action_type": self.action_type,
            "params": self.params,
            "mode": self.mode,
            "result": self.result,
            "snapshot_ref": self.snapshot_ref,
            "reasons": self.reasons,
            "rollback_of": self.rollback_of,
            "directive_version": self.directive_version,
        }

    @classmethod
    def from_json_dict(cls, d: dict) -> "ActionRecord":
        return cls(
            id=d["id"],
            timestamp=d["timestamp"],
            agent=d["agent"],
            action_type=d["action_type"],
            params=d.get("params", {}),
            mode=d["mode"],
            result=d["result"],
            snapshot_ref=d.get("snapshot_ref"),
            reasons=d.get("reasons", []),
            rollback_of=d.get("rollback_of"),
            directive_version=d.get("directive_version", ""),
        )
