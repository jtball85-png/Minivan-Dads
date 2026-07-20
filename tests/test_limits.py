"""Loader tests: limits.yaml parsing/fail-fast and capabilities.yaml round-trip."""

from __future__ import annotations

import pytest

from brain.actions.limits import (
    demote,
    load_capabilities,
    load_limits,
    write_capability,
)
from brain.actions.models import ActionMode
from brain.actions.registry import REGISTRY


def test_shipped_limits_yaml_loads_against_real_registry():
    limits = load_limits(registry=REGISTRY)
    assert set(limits) == {"creative", "storefront", "paid_ads", "content"}
    assert limits["creative"].allowed_actions == ["printful.create_product"]
    assert limits["creative"].daily_action_cap == 5
    assert limits["storefront"].daily_action_cap == 10
    assert limits["storefront"].action_bounds["shopify.set_price"]["requires"] == "escalation"
    assert limits["paid_ads"].action_bounds["meta.adjust_budget"]["weekly_total_cap_usd"] == 50
    assert limits["content"].publish_window == "06:00-21:00"
    assert limits["content"].daily_action_cap == 2  # max_posts_per_day

def test_unknown_action_name_fails_fast(tmp_path):
    bad = tmp_path / "limits.yaml"
    bad.write_text(
        "storefront:\n  allowed_actions: [shopify.update_listing_copyy]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unregistered action"):
        load_limits(path=bad, registry=REGISTRY)


def test_unknown_bound_key_fails(tmp_path):
    bad = tmp_path / "limits.yaml"
    bad.write_text(
        "storefront:\n  allowed_actions: []\n  bounds:\n    mystery_knob: 5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown bound key"):
        load_limits(path=bad, registry=REGISTRY)


def test_missing_limits_file_returns_empty(tmp_path):
    assert load_limits(path=tmp_path / "absent.yaml", registry=REGISTRY) == {}


def test_capabilities_missing_file_returns_empty(tmp_path):
    assert load_capabilities(tmp_path / "absent.yaml") == {}


def test_write_capability_round_trip(tmp_path):
    path = tmp_path / "capabilities.yaml"
    write_capability(path, "storefront", "shopify.update_listing_copy",
                     ActionMode.SUPERVISED, note="promoted per DEC-041")
    caps = load_capabilities(path)
    assert caps["storefront"]["shopify.update_listing_copy"] == ActionMode.SUPERVISED
    content = path.read_text(encoding="utf-8")
    assert "MACHINE-OWNED" in content
    assert "DEC-041" in content


def test_write_capability_preserves_other_entries(tmp_path):
    path = tmp_path / "capabilities.yaml"
    write_capability(path, "storefront", "a.one", ActionMode.AUTO, note="n1")
    # Register fake names isn't needed — capabilities are validated at use time
    write_capability(path, "content", "b.two", ActionMode.SUPERVISED, note="n2")
    caps = load_capabilities(path)
    assert caps["storefront"]["a.one"] == ActionMode.AUTO
    assert caps["content"]["b.two"] == ActionMode.SUPERVISED


def test_demote_ladder():
    assert demote(ActionMode.AUTO) == ActionMode.SUPERVISED
    assert demote(ActionMode.SUPERVISED) == ActionMode.DRY_RUN
    assert demote(ActionMode.DRY_RUN) == ActionMode.DRY_RUN
