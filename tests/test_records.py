"""Tests for the shared records machinery (brain/records.py)."""

from __future__ import annotations

import re
from datetime import date

from brain.records import (
    extract_directive_updates,
    parse_decision_entries,
    split_sections,
    tier_or_status_changed,
)

SECTION_RE = re.compile(r"^## (Alpha|Beta)\s*$", re.MULTILINE)


class TestSplitSections:
    def test_splits_on_known_headings_only(self):
        md = "## Alpha\n\nbody a\n\n## Unknown\n\nstill alpha\n\n## Beta\n\nbody b"
        sections = split_sections(md, SECTION_RE)
        assert "## Unknown" in sections["Alpha"]
        assert sections["Beta"] == "body b"

    def test_internal_headings_do_not_break_split(self):
        md = "## Alpha\n\n## Tier\n\nTier 0\n\n## Mandate\n\nwatch\n\n## Beta\n\nend"
        sections = split_sections(md, SECTION_RE)
        assert "## Tier" in sections["Alpha"]
        assert "## Mandate" in sections["Alpha"]


class TestParseDecisionEntries:
    def test_parses_fields_and_departments(self):
        body = (
            "### Ship the thing\n"
            "- Rationale: it is time. Dissents: none\n"
            "- Decided by: CEO\n"
            "- Affected departments: creative, content\n"
        )
        entries = parse_decision_entries(body, as_of=date(2026, 7, 16))
        assert len(entries) == 1
        assert entries[0].title == "Ship the thing"
        assert entries[0].departments == ["creative", "content"]
        assert entries[0].date == date(2026, 7, 16)

    def test_none_departments_is_empty_list(self):
        body = "### T\n- Rationale: r\n- Decided by: CEO\n- Affected departments: none\n"
        assert parse_decision_entries(body)[0].departments == []


class TestExtractDirectiveUpdates:
    def test_none_literal_returns_nothing(self):
        updates, warnings = extract_directive_updates("None.", ["creative"])
        assert updates == {} and warnings == []

    def test_fenced_content_extracted(self):
        body = "### creative\n\n```markdown\n# Directive: Creative\n\n## Tier\n\nTier 1\n```\n"
        updates, warnings = extract_directive_updates(body, ["creative"])
        assert warnings == []
        assert updates["creative"].startswith("# Directive: Creative")
        assert "## Tier" in updates["creative"]

    def test_unknown_department_warned_and_skipped(self):
        body = "### mystery\n\n```markdown\nx\n```\n"
        updates, warnings = extract_directive_updates(body, ["creative"])
        assert updates == {}
        assert "unknown department" in warnings[0]

    def test_unfenced_content_warned_and_skipped(self):
        body = "### creative\n\nJust prose, no fence.\n"
        updates, warnings = extract_directive_updates(body, ["creative"])
        assert updates == {}
        assert "fenced" in warnings[0]

    def test_braced_department_placeholder_normalized(self):
        body = "### {creative}\n\n```markdown\n# Directive: Creative\n```\n"
        updates, _ = extract_directive_updates(body, ["creative"])
        assert "creative" in updates


HEADING_STYLE = "# Directive: Creative\n\n## Tier\n\nTier 0 — Read-only\n\n## Status\n\ndormant\n"
BOLD_STYLE = "# Creative\n\n**Tier:** Tier 1 — Draft-only\n\n**Status:** Active\n"


class TestTierOrStatusChanged:
    def test_detects_tier_and_status_change_across_styles(self):
        change = tier_or_status_changed(HEADING_STYLE, BOLD_STYLE)
        assert "tier 0 -> 1" in change
        assert "status dormant -> active" in change

    def test_no_change_returns_none(self):
        assert tier_or_status_changed(HEADING_STYLE, HEADING_STYLE) is None

    def test_same_tier_reworded_directive_is_fine(self):
        rewrite = "# Directive: Creative\n\n## Tier\n\nTier 0 — Read-only\n\n## Status\n\ndormant\n\n## Standing orders\n\nNew orders here.\n"
        assert tier_or_status_changed(HEADING_STYLE, rewrite) is None

    def test_undetectable_fields_do_not_false_positive(self):
        # Proposed content with no recognizable tier/status lines: no basis
        # to claim a change, so the guard stays quiet.
        assert tier_or_status_changed(HEADING_STYLE, "# Something minimal\n") is None
