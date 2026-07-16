"""The executor — the ONLY module allowed to make external write calls.

Agents propose ActionIntents; prompts express intent, this module enforces
law. A confused, buggy, or manipulated agent must be UNABLE — not just
instructed not — to exceed its authority.

Validation order in submit() (first failure short-circuits to rejection):

  1. Global kill switch (EXECUTOR_ENABLED env var; unset = enabled — safe
     because every capability defaults to dry-run). When off, EVERYTHING is
     rejected, dry-runs included: total silence is the point.
  2. Agent known and not suspended.
  3. Action type registered (unregistered action = impossible action).
  4. Params match the schema (missing, extra, or mistyped all reject —
     no smuggling).
  5. Hardcoded global denials — checked BEFORE limits.yaml so yaml can
     never permit them.
  6. Agent allowlist.
  7. Bounds: requires-escalation, max-change %, single-change and weekly
     caps (summed from the action log; dry-runs don't count), daily action
     cap, publish window.
  8. Mode resolution from the capability ladder. Irreversible actions run
     one rung lower than granted (auto -> supervised -> dry-run) because
     they can't be rolled back.

Every rejection is logged AND escalated — never silently dropped.
Live path: log an 'executing' line BEFORE touching the connector (a crash
mid-call leaves evidence), snapshot BEFORE execute (snapshot failure =
rejected, never executed), then log 'executed' or 'failed'.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Callable, Mapping, Protocol

from brain.actions.limits import AgentLimits, demote, write_capability
from brain.actions.models import (
    ActionIntent,
    ActionMode,
    ActionRecord,
    ActionResult,
    ActionType,
)
from brain.actions.registry import is_hard_denied
from brain.hq import HQ
from brain.models import EscalationItem

PUBLISH_WINDOW_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")

_TYPE_CHECKS: dict[str, Callable] = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
}


class Connector(Protocol):
    """The interface every platform connector implements. Only the executor
    calls execute/restore; agents may use read methods elsewhere freely."""

    def read_state(self, action_type: ActionType, params: dict) -> dict: ...
    def execute(self, action_type: ActionType, params: dict) -> dict: ...
    def restore(self, action_type: ActionType, snapshot: dict) -> dict: ...


class Executor:
    def __init__(
        self,
        hq: HQ,
        registry: dict[str, ActionType],
        limits: dict[str, AgentLimits],
        capabilities: dict[str, dict[str, ActionMode]],
        connectors: dict[str, Connector],
        capabilities_path=None,
        env: Mapping = os.environ,
        now_fn: Callable[[], datetime] = datetime.now,
    ):
        self.hq = hq
        self.registry = registry
        self.limits = limits
        self.capabilities = capabilities
        self.connectors = connectors
        self.capabilities_path = capabilities_path or (hq.root / "actions" / "capabilities.yaml")
        self.env = env
        self.now_fn = now_fn

    # ------------------------------------------------------------------

    def submit(self, intent: ActionIntent) -> ActionRecord:
        action_id = self.hq.next_action_id(as_of=self.now_fn().date())

        reasons = self._validate(intent)
        if reasons:
            record = self._record(action_id, intent, mode="", result=ActionResult.REJECTED,
                                  reasons=reasons)
            self.hq.append_action(record)
            self._escalate_rejection(intent, reasons)
            return record

        action_type = self.registry[intent.action_type]
        mode = self._resolve_mode(intent.agent, action_type)

        # Live modes need a connector before anything else can be verified.
        connector = self.connectors.get(action_type.connector)
        if mode != ActionMode.DRY_RUN and connector is None:
            reasons = [f"no live connector installed for {action_type.connector!r} (Phase 2+)"]
            record = self._record(action_id, intent, mode=mode.value,
                                  result=ActionResult.REJECTED, reasons=reasons)
            self.hq.append_action(record)
            self._escalate_rejection(intent, reasons)
            return record

        # Bounds (step 7) come after mode resolution: connector-dependent
        # checks (max_change_pct) are skipped for dry-runs, which execute
        # nothing — they're re-verified for real once the capability is live.
        reasons = self._check_bounds(intent, action_type,
                                     self.limits[intent.agent], mode, connector)
        if reasons:
            record = self._record(action_id, intent, mode=mode.value,
                                  result=ActionResult.REJECTED, reasons=reasons)
            self.hq.append_action(record)
            self._escalate_rejection(intent, reasons)
            return record

        if mode == ActionMode.DRY_RUN:
            record = self._record(action_id, intent, mode=mode.value, result=ActionResult.DRY_RUN)
            self.hq.append_action(record)
            return record

        return self._execute_live(action_id, intent, action_type, mode, connector)

    def _execute_live(self, action_id: str, intent: ActionIntent,
                      action_type: ActionType, mode: ActionMode,
                      connector: Connector) -> ActionRecord:
        # Evidence before action: a crash mid-call must leave a trace.
        self.hq.append_action(
            self._record(action_id, intent, mode=mode.value, result=ActionResult.EXECUTING)
        )

        # Snapshot before execute. Snapshot failure = rejected, never executed.
        snapshot_ref: str | None = None
        if action_type.snapshot_params:
            try:
                state = connector.read_state(action_type, intent.params)
                snapshot_ref = str(self.hq.write_snapshot(action_id, state))
            except Exception as e:
                record = self._record(action_id, intent, mode=mode.value,
                                      result=ActionResult.REJECTED,
                                      reasons=[f"pre-action snapshot failed: {e} — refusing to execute"])
                self.hq.append_action(record)
                self._escalate_rejection(intent, record.reasons)
                return record

        try:
            connector.execute(action_type, intent.params)
        except Exception as e:
            record = self._record(action_id, intent, mode=mode.value, result=ActionResult.FAILED,
                                  snapshot_ref=snapshot_ref, reasons=[str(e)])
            self.hq.append_action(record)
            return record

        record = self._record(action_id, intent, mode=mode.value, result=ActionResult.EXECUTED,
                              snapshot_ref=snapshot_ref)
        self.hq.append_action(record)
        return record

    # ------------------------------------------------------------------

    def rollback(self, action_id: str) -> ActionRecord:
        """Restore the pre-action snapshot, then demote the capability one
        rung — a rollback is the system telling itself trust was misplaced."""
        records = {r.id: r for r in self.hq.read_actions()}
        record = records.get(action_id)
        if record is None:
            raise ValueError(f"No action {action_id!r} in the log.")
        if record.result != ActionResult.EXECUTED:
            raise ValueError(f"{action_id} is {record.result!r}, not executed — nothing to roll back.")
        action_type = self.registry.get(record.action_type)
        if action_type is None:
            raise ValueError(f"{action_id} has unregistered type {record.action_type!r}.")
        if action_type.irreversible:
            raise ValueError(f"{record.action_type} is irreversible — no rollback exists.")
        if not record.snapshot_ref:
            raise ValueError(f"{action_id} has no snapshot — cannot restore.")

        connector = self.connectors.get(action_type.connector)
        if connector is None:
            raise ValueError(f"No live connector for {action_type.connector!r}.")

        snapshot = self.hq.read_snapshot(action_id)
        connector.restore(action_type, snapshot)

        rollback_record = ActionRecord(
            id=action_id,
            timestamp=self.now_fn().isoformat(timespec="seconds"),
            agent=record.agent,
            action_type=record.action_type,
            params=record.params,
            mode=record.mode,
            result=ActionResult.ROLLED_BACK,
            snapshot_ref=record.snapshot_ref,
            rollback_of=action_id,
            directive_version=record.directive_version,
        )
        self.hq.append_action(rollback_record)

        # Automatic demotion (capability ladder §5.4).
        current = self.capabilities.get(record.agent, {}).get(
            record.action_type, ActionMode.DRY_RUN
        )
        demoted = demote(current)
        if demoted != current:
            self.capabilities.setdefault(record.agent, {})[record.action_type] = demoted
            write_capability(
                self.capabilities_path, record.agent, record.action_type, demoted,
                note=f"auto-demoted {current.value} -> {demoted.value} after rollback of {action_id}",
            )
        self.hq.append_escalation(
            EscalationItem(
                id="",
                raised=self.now_fn().date(),
                raised_by=f"executor/{record.agent}",
                urgency="normal",
                summary=(
                    f"{record.action_type} rolled back ({action_id}); capability demoted "
                    f"{current.value} -> {demoted.value}. Raise at the next board meeting."
                ),
            )
        )
        return rollback_record

    # ------------------------------------------------------------------

    def _validate(self, intent: ActionIntent) -> list[str]:
        # 1. Kill switch — unset means enabled (dry-run default keeps that safe).
        raw = str(self.env.get("EXECUTOR_ENABLED", "true")).strip().lower()
        if raw in ("false", "0", "no"):
            return ["EXECUTOR_ENABLED is off — all actions refused"]

        # 2. Agent known + not suspended.
        dept = self.hq.config.departments.get(intent.agent)
        if dept is None:
            return [f"unknown agent {intent.agent!r}"]
        if dept.status == "suspended":
            return [f"agent {intent.agent!r} is suspended"]

        # 3. Registered.
        action_type = self.registry.get(intent.action_type)
        if action_type is None:
            return [f"unregistered action {intent.action_type!r} — unregistered means impossible"]

        # 4. Params match schema.
        reasons = []
        missing = set(action_type.params) - set(intent.params)
        extra = set(intent.params) - set(action_type.params)
        if missing:
            reasons.append(f"missing params: {', '.join(sorted(missing))}")
        if extra:
            reasons.append(f"unexpected params: {', '.join(sorted(extra))}")
        for name, type_name in action_type.params.items():
            if name in intent.params and not _TYPE_CHECKS[type_name](intent.params[name]):
                reasons.append(f"param {name!r} is not {type_name}")
        if reasons:
            return reasons

        # 5. Hard global denials — before yaml, so yaml can never permit them.
        if action_type.always_escalate or is_hard_denied(intent.action_type):
            return [f"{intent.action_type} is globally denied (hardcoded) — always escalates to the CEO"]

        # 6. Allowlist. (Bounds — step 7 — run in submit() after mode
        # resolution, since some checks are connector-dependent.)
        agent_limits = self.limits.get(intent.agent)
        if agent_limits is None or intent.action_type not in agent_limits.allowed_actions:
            return [f"{intent.action_type} is not in {intent.agent}'s allowed_actions"]

        return []

    def _check_bounds(self, intent: ActionIntent, action_type: ActionType,
                      agent_limits: AgentLimits, mode: ActionMode,
                      connector: Connector | None) -> list[str]:
        bounds = agent_limits.action_bounds.get(intent.action_type, {})

        if bounds.get("requires") == "escalation":
            return [f"{intent.action_type} requires escalation per limits.yaml"]

        # Dry-runs touch nothing external — not even reads. Connector-backed
        # checks are re-verified for real once the capability goes live.
        if "max_change_pct" in bounds and connector is not None and mode != ActionMode.DRY_RUN:
            state = connector.read_state(action_type, intent.params)
            current = float(state.get("current_value", 0))
            new = self._numeric_param(intent.params)
            if current > 0 and new is not None:
                change_pct = abs(new - current) / current * 100
                if change_pct > bounds["max_change_pct"]:
                    return [f"change of {change_pct:.0f}% exceeds max_change_pct {bounds['max_change_pct']}"]

        if "max_single_change_usd" in bounds:
            new = self._numeric_param(intent.params)
            if new is not None and new > bounds["max_single_change_usd"]:
                return [f"${new:.2f} exceeds max_single_change_usd ${bounds['max_single_change_usd']}"]

        now = self.now_fn()
        if "weekly_total_cap_usd" in bounds:
            week_start = now.date() - timedelta(days=now.date().weekday())
            spent = sum(
                self._numeric_param(r.params) or 0
                for r in self.hq.read_actions(since=week_start)
                if r.agent == intent.agent
                and r.action_type == intent.action_type
                and r.result == ActionResult.EXECUTED  # dry-runs are free
            )
            new = self._numeric_param(intent.params) or 0
            if spent + new > bounds["weekly_total_cap_usd"]:
                return [
                    f"${spent + new:.2f} this week would exceed weekly_total_cap_usd "
                    f"${bounds['weekly_total_cap_usd']} (${spent:.2f} already executed)"
                ]

        if agent_limits.daily_action_cap is not None:
            today_count = sum(
                1 for r in self.hq.read_actions(since=now.date())
                if r.agent == intent.agent and r.result == ActionResult.EXECUTED
            )
            if today_count >= agent_limits.daily_action_cap:
                return [f"daily action cap ({agent_limits.daily_action_cap}) reached"]

        if agent_limits.publish_window is not None:
            m = PUBLISH_WINDOW_RE.match(agent_limits.publish_window)
            if m:
                start = int(m.group(1)) * 60 + int(m.group(2))
                end = int(m.group(3)) * 60 + int(m.group(4))
                minute_of_day = now.hour * 60 + now.minute
                if not (start <= minute_of_day <= end):
                    return [f"outside publish window {agent_limits.publish_window}"]

        return []

    @staticmethod
    def _numeric_param(params: dict) -> float | None:
        """First numeric (non-bool) param value — budgets/prices for bound checks."""
        for v in params.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None

    def _resolve_mode(self, agent: str, action_type: ActionType) -> ActionMode:
        granted = self.capabilities.get(agent, {}).get(action_type.name, ActionMode.DRY_RUN)
        if action_type.irreversible:
            return demote(granted)  # irreversible runs one rung lower than granted
        return granted

    def _record(self, action_id: str, intent: ActionIntent, mode: str,
                result: ActionResult, snapshot_ref: str | None = None,
                reasons: list[str] | None = None) -> ActionRecord:
        return ActionRecord(
            id=action_id,
            timestamp=self.now_fn().isoformat(timespec="seconds"),
            agent=intent.agent,
            action_type=intent.action_type,
            params=intent.params,
            mode=mode,
            result=result,
            snapshot_ref=snapshot_ref,
            reasons=reasons or [],
            directive_version=intent.directive_version,
        )

    def _escalate_rejection(self, intent: ActionIntent, reasons: list[str]) -> None:
        self.hq.append_escalation(
            EscalationItem(
                id="",
                raised=self.now_fn().date(),
                raised_by=f"executor/{intent.agent}",
                urgency="normal",
                summary=(
                    f"Action rejected: {intent.action_type} — {'; '.join(reasons)}. "
                    f"Agent rationale: {intent.rationale or '(none given)'}"
                ),
            )
        )
