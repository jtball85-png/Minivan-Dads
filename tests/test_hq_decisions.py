from datetime import date

from brain.models import DecisionEntry


def test_append_decision_creates_log_if_missing(hq):
    hq.append_decision(
        DecisionEntry(date=date(2026, 7, 15), title="Test decision", rationale="because", decided_by="CEO")
    )
    assert (hq.root / "decisions" / "log.md").exists()


def test_append_decision_preserves_existing_content_as_exact_prefix(hq):
    log_path = hq.root / "decisions" / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    seed = "# Decision Log\n\nAppend-only.\n" + ("existing entry text " * 200)
    log_path.write_text(seed, encoding="utf-8")

    hq.append_decision(DecisionEntry(date=date(2026, 7, 15), title="New", rationale="r", decided_by="CEO"))

    after = log_path.read_text(encoding="utf-8")
    assert after.startswith(seed)
    assert "New" in after


def test_append_decision_twice_leaves_first_entry_byte_identical(hq):
    hq.append_decision(DecisionEntry(date=date(2026, 7, 15), title="First", rationale="r1", decided_by="CEO"))
    log_path = hq.root / "decisions" / "log.md"
    after_first = log_path.read_text(encoding="utf-8")

    hq.append_decision(DecisionEntry(date=date(2026, 7, 16), title="Second", rationale="r2", decided_by="CEO"))
    after_second = log_path.read_text(encoding="utf-8")

    assert after_second.startswith(after_first)


def test_read_decisions_order_and_limit(hq):
    for i in range(3):
        hq.append_decision(
            DecisionEntry(date=date(2026, 7, 10 + i), title=f"D{i}", rationale="r", decided_by="CEO")
        )
    decisions = hq.read_decisions(limit=2)
    assert [d.title for d in decisions] == ["D1", "D2"]


def test_read_decisions_empty_or_missing_log_returns_empty_list(hq):
    assert hq.read_decisions() == []


def test_read_decisions_parses_departments(hq):
    hq.append_decision(
        DecisionEntry(
            date=date(2026, 7, 15),
            title="D",
            rationale="r",
            decided_by="CEO",
            departments=["market_intel", "creative"],
        )
    )
    decisions = hq.read_decisions()
    assert decisions[0].departments == ["market_intel", "creative"]


def test_read_decisions_no_departments_parses_as_empty_list(hq):
    hq.append_decision(DecisionEntry(date=date(2026, 7, 15), title="D", rationale="r", decided_by="CEO"))
    decisions = hq.read_decisions()
    assert decisions[0].departments == []
