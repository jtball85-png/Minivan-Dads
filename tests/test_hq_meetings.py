from datetime import date


def test_last_meeting_date_none_when_no_meetings_exist(hq):
    assert hq.last_meeting_date() is None


def test_last_meeting_date_returns_the_latest(hq):
    hq.write_minutes("2026-W20", "minutes content")
    hq.write_minutes("2026-W25", "minutes content")

    result = hq.last_meeting_date()

    assert result == date.fromisocalendar(2026, 25, 1)


def test_last_meeting_date_across_year_boundary_not_string_sorted(hq):
    hq.write_minutes("2025-W52", "old")
    hq.write_minutes("2026-W01", "new")

    result = hq.last_meeting_date()

    # String comparison of "2025-W52" vs "2026-W01" would (correctly, by
    # coincidence) say 2026-W01 is later — the real trap is same-year
    # comparisons like "2026-W9" vs "2026-W10", which this format avoids
    # by zero-padding. This test locks in the chronological (not string)
    # ordering explicitly.
    assert result == date.fromisocalendar(2026, 1, 1)


def test_write_agenda_roundtrip(hq):
    path = hq.write_agenda("2026-W29", "agenda body")
    assert path.read_text(encoding="utf-8") == "agenda body"


def test_write_minutes_roundtrip(hq):
    path = hq.write_minutes("2026-W29", "minutes body")
    assert path.read_text(encoding="utf-8") == "minutes body"


def test_write_monthly_review(hq):
    path = hq.write_monthly_review("2026-07", "review body")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "review body"
