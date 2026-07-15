from datetime import date

from brain.models import ReportStatus


def test_week_key_for_date_matches_iso_calendar(hq):
    d = date(2026, 7, 15)
    iso_year, iso_week, _ = d.isocalendar()
    assert hq.week_key_for_date(d) == f"{iso_year}-W{iso_week:02d}"


def test_week_key_for_date_year_boundary_uses_iso_year(hq):
    d = date(2025, 12, 29)
    iso_year, iso_week, _ = d.isocalendar()
    key = hq.week_key_for_date(d)
    assert key == f"{iso_year}-W{iso_week:02d}"
    # This date's ISO year diverges from its calendar year — proves the
    # implementation isn't naively splitting on d.year.
    assert iso_year != d.year


def test_current_week_key_honors_as_of(hq):
    as_of = date(2025, 12, 29)
    iso_year, iso_week, _ = as_of.isocalendar()
    assert hq.current_week_key(as_of=as_of) == f"{iso_year}-W{iso_week:02d}"


def test_previous_week_key_is_seven_days_earlier(hq):
    as_of = date(2026, 7, 15)
    expected = hq.week_key_for_date(date(2026, 7, 8))
    assert hq.previous_week_key(as_of=as_of) == expected


def test_report_path(hq):
    path = hq.report_path("market_intel", "2026-W29")
    assert path == hq.root / "reports" / "market_intel" / "2026-W29.md"


def test_read_report_missing_returns_none(hq):
    assert hq.read_report("market_intel", "2026-W29") is None


def test_read_report_existing(hq):
    report_dir = hq.root / "reports" / "market_intel"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "2026-W29.md").write_text("Weekly findings...", encoding="utf-8")
    assert hq.read_report("market_intel", "2026-W29") == "Weekly findings..."


def test_reports_status_three_way(hq):
    report_dir = hq.root / "reports" / "market_intel"
    report_dir.mkdir(parents=True, exist_ok=True)
    week = hq.current_week_key()
    (report_dir / f"{week}.md").write_text("report", encoding="utf-8")

    status = hq.reports_status()

    assert status["market_intel"] == ReportStatus.FILED
    assert status["creative"] == ReportStatus.DORMANT


def test_reports_status_missing_for_active_dept_with_no_file(hq):
    status = hq.reports_status()
    assert status["market_intel"] == ReportStatus.MISSING


def test_discover_reports_cutoff_across_year_boundary(hq):
    report_dir = hq.root / "reports" / "market_intel"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "2025-W52.md").write_text("old", encoding="utf-8")
    (report_dir / "2026-W01.md").write_text("new", encoding="utf-8")

    entries = hq.discover_reports(since_week_key="2026-W01")

    weeks = [e.week_key for e in entries["market_intel"]]
    assert weeks == ["2026-W01"]


def test_discover_reports_missing_dept_dir_returns_empty(hq):
    entries = hq.discover_reports(since_week_key="2026-W01")
    assert entries["creative"] == []


def test_discover_reports_empty_dept_dir_returns_empty(hq):
    (hq.root / "reports" / "market_intel").mkdir(parents=True, exist_ok=True)
    entries = hq.discover_reports(since_week_key="2026-W01")
    assert entries["market_intel"] == []
