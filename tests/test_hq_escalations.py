from datetime import date

import pytest

from brain.models import EscalationItem


def make_item(escalation_id="", urgency="normal", raised_by="market_intel", summary="test"):
    return EscalationItem(id=escalation_id, raised=date(2026, 7, 15), raised_by=raised_by, urgency=urgency, summary=summary)


def test_append_escalation_assigns_sequential_ids(hq):
    id1 = hq.append_escalation(make_item())
    id2 = hq.append_escalation(make_item())
    assert id1 == "ESC-001"
    assert id2 == "ESC-002"


def test_resolve_escalation_moves_item_to_resolved(hq):
    eid = hq.append_escalation(make_item(summary="thing to resolve"))
    hq.resolve_escalation(eid, resolution="fixed", decided_by="CEO", as_of=date(2026, 7, 16))

    queue = hq.read_escalation_queue()
    resolved = hq.read_resolved_escalations()

    assert all(item.id != eid for item in queue)
    match = next(item for item in resolved if item.id == eid)
    assert match.resolution == "fixed"
    assert match.decided_by == "CEO"
    assert match.resolved == date(2026, 7, 16)


def test_resolving_one_item_leaves_others_intact(hq):
    id1 = hq.append_escalation(make_item(summary="first"))
    id2 = hq.append_escalation(make_item(summary="second"))
    id3 = hq.append_escalation(make_item(summary="third"))

    hq.resolve_escalation(id2, resolution="done", decided_by="CEO")

    queue_text = (hq.root / "escalations" / "queue.md").read_text(encoding="utf-8")
    assert f"## {id1}" in queue_text
    assert f"## {id3}" in queue_text
    assert f"## {id2}" not in queue_text


def test_resolve_nonexistent_id_raises_with_no_partial_writes(hq):
    hq.append_escalation(make_item())
    queue_path = hq.root / "escalations" / "queue.md"
    resolved_path = hq.root / "escalations" / "resolved.md"
    before_queue = queue_path.read_text(encoding="utf-8")
    resolved_existed = resolved_path.exists()

    with pytest.raises(ValueError):
        hq.resolve_escalation("ESC-999", resolution="n/a", decided_by="CEO")

    assert queue_path.read_text(encoding="utf-8") == before_queue
    assert resolved_path.exists() == resolved_existed


def test_resolve_escalation_atomic_write_failure_leaves_queue_unchanged(hq, monkeypatch):
    eid = hq.append_escalation(make_item())
    queue_path = hq.root / "escalations" / "queue.md"
    before = queue_path.read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("simulated failure")

    monkeypatch.setattr("brain.hq.os.replace", boom)

    with pytest.raises(OSError):
        hq.resolve_escalation(eid, resolution="x", decided_by="CEO")

    assert queue_path.read_text(encoding="utf-8") == before
    assert not (hq.root / "escalations" / "resolved.md").exists()


def test_read_escalation_queue_sorts_urgent_first(hq):
    hq.append_escalation(make_item(urgency="normal", summary="normal one"))
    urgent_id = hq.append_escalation(make_item(urgency="urgent", summary="urgent one"))

    queue = hq.read_escalation_queue()

    assert queue[0].id == urgent_id
    assert queue[0].urgency == "urgent"


def test_read_escalation_queue_empty_returns_empty_list(hq):
    assert hq.read_escalation_queue() == []
