"""The storefront agent as a *doing* agent: it proposes ### ACTION blocks that
run_agent routes through the real Executor, which governs each — copy edits are
previewed (dry-run) by default, price changes are rejected-and-escalated to the
CEO. The agent never touches a platform directly."""

from __future__ import annotations

from brain.actions.limits import AgentLimits
from brain.actions.models import ActionResult
from brain.actions.registry import REGISTRY
from brain.agent import parse_actions, run_agent
from brain.executor import Executor
from brain.models import DepartmentConfig
from tests.fake_connector import FakeConnector
from tests.fake_llm import FakeLLM

REPORT = """# Storefront Report — WEEK

## Findings

1. The Quiet Game tee name could be sharper for SEO.

## Proposed changes

### ACTION
- Type: printful.update_product
- Params: {"external_id": "mvd-quiet-game-tee", "name": "Let's Play the Quiet Game — Dad Joke Tee"}
- Rationale: tighter, more searchable product name.

### ACTION
- Type: printful.set_retail_price
- Params: {"external_id": "mvd-quiet-game-tee", "retail_price": 28.0}
- Rationale: $28 gives a healthy margin over the ~$14 base.

## Escalations

None.
"""


class StorefrontFakeLLM(FakeLLM):
    def call_with_web_search(self, system_blocks, user_message, max_tokens=8192,
                             max_searches=8, extra_tools=None, tool_executor=None):
        return self.call(system_blocks, user_message, max_tokens)


class TestParseActions:
    def test_parses_action_blocks_with_json_params(self):
        actions = parse_actions(REPORT)
        assert len(actions) == 2
        assert actions[0][0] == "printful.update_product"
        assert actions[0][1]["name"].startswith("Let's Play")
        assert actions[1][0] == "printful.set_retail_price"
        assert actions[1][1]["retail_price"] == 28.0

    def test_malformed_json_is_skipped_not_executed(self):
        bad = "### ACTION\n- Type: printful.update_product\n- Params: {not json}\n- Rationale: x"
        assert parse_actions(bad) == []

    def test_no_action_blocks_yields_empty(self):
        assert parse_actions("## Findings\n\nnothing here") == []


def _storefront_env(config, hq, tmp_hq_root):
    config.departments["storefront"] = DepartmentConfig(
        name="storefront", tier=1, status="active", report_cadence="weekly")
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives" / "storefront.md").write_text(
        "# Directive: Storefront\n\nLast updated: 2026-07-20\n\nKeep products healthy.\n",
        encoding="utf-8")
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "agent_core.md").write_text("# agent core", encoding="utf-8")

    limits = {"storefront": AgentLimits(
        allowed_actions=["printful.update_product"], daily_action_cap=10)}
    executor = Executor(
        hq=hq, registry=REGISTRY, limits=limits, capabilities={},
        connectors={"printful": FakeConnector()},
        capabilities_path=tmp_hq_root / "actions" / "capabilities.yaml", env={})
    return executor


class TestStorefrontRunRoutesActions:
    def test_allowed_edit_dry_runs_and_price_escalates(self, config, hq, tmp_hq_root):
        executor = _storefront_env(config, hq, tmp_hq_root)
        llm = StorefrontFakeLLM(responses=[REPORT])

        run_agent("storefront", config, hq, llm, print_fn=lambda s: None,
                  executor=executor, product_catalog="### Catalog\n\nQuiet Game Tee")

        records = {r.action_type: r for r in hq.read_actions()}
        # Copy edit is allowed but ungranted -> previewed (dry-run), nothing live.
        assert records["printful.update_product"].result == ActionResult.DRY_RUN
        # Price is not in allowed_actions -> rejected and escalated to the CEO.
        assert records["printful.set_retail_price"].result == ActionResult.REJECTED

        queue = hq.read_escalation_queue()
        assert any("set_retail_price" in e.summary for e in queue)

    def test_catalog_injected_into_agent_context(self, config, hq, tmp_hq_root):
        executor = _storefront_env(config, hq, tmp_hq_root)
        llm = StorefrontFakeLLM(responses=[REPORT])
        run_agent("storefront", config, hq, llm, print_fn=lambda s: None,
                  executor=executor, product_catalog="### Catalog\n\nQuiet Game Tee")
        dynamic = llm.calls[0].system_blocks[1]["text"]
        assert "Current product catalog" in dynamic
        assert "Quiet Game Tee" in dynamic

    def test_reporter_only_run_ignores_actions(self, config, hq, tmp_hq_root):
        """Without an executor (a reporter department), ### ACTION blocks are
        inert text — nothing is submitted."""
        _storefront_env(config, hq, tmp_hq_root)
        llm = StorefrontFakeLLM(responses=[REPORT])
        run_agent("storefront", config, hq, llm, print_fn=lambda s: None)  # no executor
        assert hq.read_actions() == []
