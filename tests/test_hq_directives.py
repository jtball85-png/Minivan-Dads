from datetime import date

import pytest


def _seed_directive(hq, dept, last_updated):
    content = (
        f"# Directive: {dept}\n\n"
        f"Last updated: {last_updated.isoformat()}\n\n"
        f"## Tier\n\nTier 0 — Read-only\n"
    )
    hq.write_directive(dept, content)


def test_stale_directives_flags_old_ones(hq):
    _seed_directive(hq, "market_intel", date(2026, 1, 1))
    _seed_directive(hq, "creative", date(2026, 7, 10))

    stale = hq.stale_directives(days=30, as_of=date(2026, 7, 15))

    assert "market_intel" in stale
    assert "creative" not in stale


def test_stale_directives_does_not_flag_freshly_seeded_stub(hq):
    _seed_directive(hq, "market_intel", date(2026, 7, 15))

    stale = hq.stale_directives(days=30, as_of=date(2026, 7, 15))

    assert "market_intel" not in stale


def test_read_directive_missing_raises(hq):
    with pytest.raises(FileNotFoundError):
        hq.read_directive("market_intel")


def test_write_and_read_directive_roundtrip(hq):
    hq.write_directive("market_intel", "directive content")
    assert hq.read_directive("market_intel") == "directive content"


def test_config_loader_produces_all_eight_departments():
    from brain.config import load_config

    config = load_config()

    assert len(config.departments) == 8
    # Phase 2/3: market_intel and creative are live; everything else stays
    # dormant until its phase (roadmap). Update this test at each
    # activation — it's the tripwire against accidental activations.
    active = {"market_intel", "creative"}
    assert all(config.departments[name].status == "active" for name in active)
    assert all(
        d.status == "dormant"
        for name, d in config.departments.items() if name not in active
    )
    assert config.departments["creative"].tier == 1
    expected = {
        "market_intel", "creative", "content", "product",
        "storefront", "customer", "paid_ads", "finance",
    }
    assert set(config.departments.keys()) == expected
