"""Executor validation matrix — the safety-critical piece, tested with fake
connectors and a fake registry so nothing external is ever touched."""

from __future__ import annotations

from datetime import datetime

import pytest

from brain.actions.limits import AgentLimits
from brain.actions.models import ActionIntent, ActionMode, ActionRecord, ActionType
from brain.executor import Executor
from brain.models import DepartmentConfig
from tests.fake_connector import FakeConnector

FAKE_REGISTRY = {
    "fake.set_value": ActionType(
        name="fake.set_value",
        connector="fake",
        params={"target_id": "str", "new_value": "float"},
        snapshot_params=("target_id",),
    ),
    "fake.post_forever": ActionType(
        name="fake.post_forever",
        connector="fake",
        params={"text": "str"},
        irreversible=True,
    ),
    "fake.touch_payment_settings": ActionType(
        name="fake.touch_payment_settings",
        connector="fake",
        params={},
        always_escalate=True,
    ),
    "fake.no_snapshot_write": ActionType(
        name="fake.no_snapshot_write",
        connector="fake",
        params={"text": "str"},
    ),
}

NOW = datetime(2026, 7, 16, 12, 0, 0)


@pytest.fixture
def agent_config(config):
    config.departments["storefront"] = DepartmentConfig(
        name="storefront", tier=1, status="active", report_cadence="weekly"
    )
    config.departments["suspended_dept"] = DepartmentConfig(
        name="suspended_dept", tier=1, status="suspended", report_cadence="weekly"
    )
    return config


@pytest.fixture
def limits():
    return {
        "storefront": AgentLimits(
            allowed_actions=["fake.set_value", "fake.post_forever", "fake.no_snapshot_write"],
            action_bounds={
                "fake.set_value": {
                    "max_change_pct": 10,
                    "max_single_change_usd": 150,
                    "weekly_total_cap_usd": 300,
                },
            },
            daily_action_cap=3,
        ),
    }


def make_executor(hq, limits, capabilities=None, connector=None, env=None, tmp_path=None):
    return Executor(
        hq=hq,
        registry=FAKE_REGISTRY,
        limits=limits,
        capabilities=capabilities or {},
        connectors={"fake": connector} if connector else {},
        capabilities_path=(tmp_path / "capabilities.yaml") if tmp_path else None,
        env=env or {},
        now_fn=lambda: NOW,
    )


def intent(action="fake.set_value", agent="storefront", params=None, rationale="test"):
    return ActionIntent(
        agent=agent,
        action_type=action,
        params={"target_id": "P1", "new_value": 105.0} if params is None else params,
        rationale=rationale,
    )


def esc_summaries(hq):
    return [e.summary for e in hq.read_escalation_queue()]


class TestValidationOrder:
    def test_kill_switch_rejects_everything_even_dry_run(self, hq, agent_config, limits):
        ex = make_executor(hq, limits, env={"EXECUTOR_ENABLED": "false"})
        record = ex.submit(intent())
        assert record.result == "rejected"
        assert "EXECUTOR_ENABLED" in record.reasons[0]
        assert esc_summaries(hq)

    def test_kill_switch_unset_means_enabled(self, hq, agent_config, limits):
        ex = make_executor(hq, limits, env={})
        record = ex.submit(intent())
        assert record.result == "dry_run"  # default capability mode

    def test_unknown_agent_rejected(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(intent(agent="nobody"))
        assert record.result == "rejected"
        assert "unknown agent" in record.reasons[0]

    def test_suspended_agent_rejected(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(intent(agent="suspended_dept"))
        assert record.result == "rejected"
        assert "suspended" in record.reasons[0]

    def test_unregistered_action_rejected(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(
            intent(action="fake.not_a_thing", params={})
        )
        assert record.result == "rejected"
        assert "unregistered" in record.reasons[0]

    def test_missing_param_rejected(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(intent(params={"target_id": "P1"}))
        assert record.result == "rejected"
        assert "missing params: new_value" in record.reasons[0]

    def test_extra_param_rejected_no_smuggling(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(
            intent(params={"target_id": "P1", "new_value": 105.0, "sneaky": "x"})
        )
        assert record.result == "rejected"
        assert any("unexpected params: sneaky" in r for r in record.reasons)

    def test_mistyped_param_rejected(self, hq, agent_config, limits):
        record = make_executor(hq, limits).submit(
            intent(params={"target_id": "P1", "new_value": "not a number"})
        )
        assert record.result == "rejected"
        assert any("not float" in r for r in record.reasons)

    def test_always_escalate_flag_denied_even_if_allowlisted(self, hq, agent_config):
        permissive = {
            "storefront": AgentLimits(allowed_actions=["fake.touch_payment_settings"])
        }
        record = make_executor(hq, permissive).submit(
            intent(action="fake.touch_payment_settings", params={})
        )
        assert record.result == "rejected"
        assert "globally denied" in record.reasons[0]

    def test_hard_denial_by_name_pattern(self, hq, agent_config):
        registry = dict(FAKE_REGISTRY)
        registry["fake.delete_everything"] = ActionType(
            name="fake.delete_everything", connector="fake", params={}
        )
        permissive = {
            "storefront": AgentLimits(allowed_actions=["fake.delete_everything"])
        }
        ex = Executor(
            hq=hq, registry=registry, limits=permissive, capabilities={},
            connectors={}, env={}, now_fn=lambda: NOW,
        )
        record = ex.submit(
            ActionIntent(agent="storefront", action_type="fake.delete_everything",
                         params={}, rationale="chaos")
        )
        assert record.result == "rejected"
        assert "globally denied" in record.reasons[0]

    def test_not_in_allowlist_rejected(self, hq, agent_config):
        record = make_executor(
            hq, {"storefront": AgentLimits(allowed_actions=[])}
        ).submit(intent())
        assert record.result == "rejected"
        assert "allowed_actions" in record.reasons[0]

    def test_requires_escalation_bound(self, hq, agent_config):
        lim = {
            "storefront": AgentLimits(
                allowed_actions=["fake.set_value"],
                action_bounds={"fake.set_value": {"requires": "escalation"}},
            )
        }
        record = make_executor(hq, lim).submit(intent())
        assert record.result == "rejected"
        assert "requires escalation" in record.reasons[0]

    def test_max_change_pct_breach(self, hq, agent_config, limits, tmp_path):
        connector = FakeConnector(current_state={"current_value": 100.0})
        caps = {"storefront": {"fake.set_value": ActionMode.AUTO}}
        ex = make_executor(hq, limits, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent(params={"target_id": "P1", "new_value": 150.0}))
        assert record.result == "rejected"
        assert "max_change_pct" in record.reasons[0]

    def test_max_single_change_breach(self, hq, agent_config, tmp_path):
        lim = {
            "storefront": AgentLimits(
                allowed_actions=["fake.set_value"],
                action_bounds={"fake.set_value": {"max_single_change_usd": 15}},
            )
        }
        record = make_executor(hq, lim, tmp_path=tmp_path).submit(
            intent(params={"target_id": "C1", "new_value": 20.0})
        )
        assert record.result == "rejected"
        assert "max_single_change_usd" in record.reasons[0]

    def test_weekly_cap_sums_executed_only(self, hq, agent_config, tmp_path):
        lim = {
            "storefront": AgentLimits(
                allowed_actions=["fake.set_value"],
                action_bounds={"fake.set_value": {"weekly_total_cap_usd": 50}},
            )
        }
        connector = FakeConnector()
        caps = {"storefront": {"fake.set_value": ActionMode.AUTO}}
        ex = make_executor(hq, lim, capabilities=caps, connector=connector, tmp_path=tmp_path)

        # Two executed actions of $20 each (this ISO week starts Mon 2026-07-13)
        ex.submit(intent(params={"target_id": "C1", "new_value": 20.0}))
        ex.submit(intent(params={"target_id": "C2", "new_value": 20.0}))
        # A dry-run $20 must NOT count toward the cap
        ex.capabilities["storefront"]["fake.set_value"] = ActionMode.DRY_RUN
        ex.submit(intent(params={"target_id": "C3", "new_value": 20.0}))
        ex.capabilities["storefront"]["fake.set_value"] = ActionMode.AUTO

        # $40 executed; $20 more would break the $50 cap
        record = ex.submit(intent(params={"target_id": "C4", "new_value": 20.0}))
        assert record.result == "rejected"
        assert "weekly_total_cap_usd" in record.reasons[0]

    def test_daily_action_cap(self, hq, agent_config, tmp_path):
        lim = {
            "storefront": AgentLimits(
                allowed_actions=["fake.no_snapshot_write"], daily_action_cap=2
            )
        }
        connector = FakeConnector()
        caps = {"storefront": {"fake.no_snapshot_write": ActionMode.AUTO}}
        ex = make_executor(hq, lim, capabilities=caps, connector=connector, tmp_path=tmp_path)
        assert ex.submit(intent(action="fake.no_snapshot_write", params={"text": "1"})).result == "executed"
        assert ex.submit(intent(action="fake.no_snapshot_write", params={"text": "2"})).result == "executed"
        record = ex.submit(intent(action="fake.no_snapshot_write", params={"text": "3"}))
        assert record.result == "rejected"
        assert "daily action cap" in record.reasons[0]

    def test_publish_window_blocks_outside_hours(self, hq, agent_config, tmp_path):
        lim = {
            "storefront": AgentLimits(
                allowed_actions=["fake.no_snapshot_write"], publish_window="06:00-21:00"
            )
        }
        connector = FakeConnector()
        caps = {"storefront": {"fake.no_snapshot_write": ActionMode.AUTO}}
        ex = Executor(
            hq=hq, registry=FAKE_REGISTRY, limits=lim, capabilities=caps,
            connectors={"fake": connector},
            capabilities_path=tmp_path / "capabilities.yaml",
            env={}, now_fn=lambda: datetime(2026, 7, 16, 23, 30),
        )
        record = ex.submit(intent(action="fake.no_snapshot_write", params={"text": "late"}))
        assert record.result == "rejected"
        assert "publish window" in record.reasons[0]


class TestExecutionPaths:
    def test_dry_run_default_no_connector_calls_one_log_line(self, hq, agent_config, limits):
        connector = FakeConnector()
        ex = make_executor(hq, limits, connector=connector)
        record = ex.submit(intent())
        assert record.result == "dry_run"
        assert connector.calls == []
        assert len(hq.read_actions()) == 1

    def test_supervised_two_phase_log_snapshot_before_execute(self, hq, agent_config, limits, tmp_path):
        connector = FakeConnector()
        caps = {"storefront": {"fake.set_value": ActionMode.SUPERVISED}}
        ex = make_executor(hq, limits, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent())

        assert record.result == "executed"
        assert record.snapshot_ref
        assert hq.read_snapshot(record.id) == {"current_value": 100.0}
        # read_state (bounds) + read_state (snapshot) + execute, in that order
        assert [c[0] for c in connector.calls] == ["read_state", "read_state", "execute"]

        # Raw log has executing then executed lines for the same id
        lines = hq.actions_log_path().read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert '"executing"' in lines[0]
        assert '"executed"' in lines[1]

    def test_snapshot_failure_rejects_and_never_executes(self, hq, agent_config, limits, tmp_path):
        connector = FakeConnector()
        caps = {"storefront": {"fake.no_snapshot_write": ActionMode.AUTO,
                                "fake.set_value": ActionMode.AUTO}}
        lim = {
            "storefront": AgentLimits(allowed_actions=["fake.set_value"])
        }
        ex = make_executor(hq, lim, capabilities=caps, connector=connector, tmp_path=tmp_path)
        connector.raise_on_read = True
        record = ex.submit(intent())
        assert record.result == "rejected"
        assert "snapshot failed" in record.reasons[0]
        assert not any(c[0] == "execute" for c in connector.calls)
        assert esc_summaries(hq)

    def test_execute_failure_logs_failed_and_keeps_snapshot(self, hq, agent_config, tmp_path):
        connector = FakeConnector()
        connector.raise_on_execute = True
        caps = {"storefront": {"fake.set_value": ActionMode.AUTO}}
        lim = {"storefront": AgentLimits(allowed_actions=["fake.set_value"])}
        ex = make_executor(hq, lim, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent())
        assert record.result == "failed"
        assert record.snapshot_ref
        assert hq.snapshot_path(record.id).exists()

    def test_irreversible_runs_one_rung_lower(self, hq, agent_config, limits, tmp_path):
        connector = FakeConnector()
        caps = {"storefront": {"fake.post_forever": ActionMode.SUPERVISED}}
        ex = make_executor(hq, limits, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent(action="fake.post_forever", params={"text": "hi"}))
        assert record.result == "dry_run"  # supervised granted -> dry-run effective
        assert connector.calls == []

    def test_no_connector_installed_rejects_live_action(self, hq, agent_config, limits):
        caps = {"storefront": {"fake.set_value": ActionMode.AUTO}}
        ex = make_executor(hq, limits, capabilities=caps)  # no connector
        record = ex.submit(intent())
        assert record.result == "rejected"
        assert "no live connector" in record.reasons[0]

    def test_every_rejection_lands_in_escalation_queue(self, hq, agent_config, limits):
        ex = make_executor(hq, limits)
        ex.submit(intent(agent="nobody"))
        summaries = esc_summaries(hq)
        assert len(summaries) == 1
        assert "Action rejected" in summaries[0]
        assert "test" in summaries[0]  # agent rationale carried through


class TestRollback:
    def _executed(self, hq, limits, tmp_path):
        connector = FakeConnector()
        caps = {"storefront": {"fake.set_value": ActionMode.AUTO}}
        ex = make_executor(hq, limits, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent())
        assert record.result == "executed"
        return ex, connector, record

    def test_happy_path_restores_and_demotes(self, hq, agent_config, limits, tmp_path):
        ex, connector, record = self._executed(hq, limits, tmp_path)
        result = ex.rollback(record.id)
        assert result.result == "rolled_back"
        assert ("restore", "fake.set_value", {"current_value": 100.0}) in connector.calls
        # Demoted auto -> supervised, persisted, escalated
        assert ex.capabilities["storefront"]["fake.set_value"] == ActionMode.SUPERVISED
        assert (tmp_path / "capabilities.yaml").exists()
        assert any("demoted" in s for s in esc_summaries(hq))

    def test_rollback_unknown_id_raises(self, hq, agent_config, limits):
        with pytest.raises(ValueError, match="No action"):
            make_executor(hq, limits).rollback("ACT-2026-W29-9999")

    def test_rollback_dry_run_refused(self, hq, agent_config, limits):
        ex = make_executor(hq, limits, connector=FakeConnector())
        record = ex.submit(intent())  # dry_run by default
        with pytest.raises(ValueError, match="not executed"):
            ex.rollback(record.id)

    def test_rollback_irreversible_refused(self, hq, agent_config, limits, tmp_path):
        connector = FakeConnector()
        caps = {"storefront": {"fake.post_forever": ActionMode.AUTO}}
        ex = make_executor(hq, limits, capabilities=caps, connector=connector, tmp_path=tmp_path)
        record = ex.submit(intent(action="fake.post_forever", params={"text": "hi"}))
        assert record.result == "executed"  # auto -> supervised effective, still live
        with pytest.raises(ValueError, match="irreversible"):
            ex.rollback(record.id)


class TestActionLog:
    def test_read_actions_last_line_wins(self, hq):
        for result in ("executing", "executed"):
            hq.append_action(ActionRecord(
                id="ACT-2026-W29-0001", timestamp="2026-07-16T12:00:00",
                agent="storefront", action_type="fake.set_value", params={},
                mode="auto", result=result,
            ))
        records = hq.read_actions()
        assert len(records) == 1
        assert records[0].result == "executed"

    def test_action_stats_counts_by_agent(self, hq):
        for i, (agent, result) in enumerate(
            [("storefront", "executed"), ("storefront", "rejected"), ("content", "dry_run")]
        ):
            hq.append_action(ActionRecord(
                id=f"ACT-2026-W29-{i:04d}", timestamp="2026-07-16T12:00:00",
                agent=agent, action_type="fake.set_value", params={},
                mode="auto", result=result,
            ))
        from datetime import date
        stats = hq.action_stats(days=7, as_of=date(2026, 7, 16))
        assert stats["storefront"] == {"executed": 1, "rejected": 1}
        assert stats["content"] == {"dry_run": 1}

    def test_read_actions_missing_file_returns_empty(self, hq):
        assert hq.read_actions() == []
