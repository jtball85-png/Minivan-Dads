"""hq/research/{slug}.md — the garage-to-board handoff point. See
CLAUDE.md's "Two rooms" section and .claude/skills/garage-research."""

from __future__ import annotations

import pytest


def test_write_then_read_round_trips(hq):
    path = hq.write_research_exhibit("dad-brand-hats-2026-07-19", "# Findings\n\nOlive/navy trend.")
    assert path.exists()
    assert hq.read_research_exhibit("dad-brand-hats-2026-07-19") == "# Findings\n\nOlive/navy trend."


def test_write_creates_the_research_directory(hq):
    hq.write_research_exhibit("first-exhibit", "content")
    assert (hq.root / "research" / "first-exhibit.md").exists()


def test_read_missing_exhibit_raises(hq):
    with pytest.raises(FileNotFoundError):
        hq.read_research_exhibit("never-written")


def test_write_overwrites_same_slug(hq):
    hq.write_research_exhibit("dad-brand-hats", "draft one")
    hq.write_research_exhibit("dad-brand-hats", "final version")
    assert hq.read_research_exhibit("dad-brand-hats") == "final version"
