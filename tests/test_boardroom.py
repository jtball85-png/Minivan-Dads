"""Boardroom protocol tests — scripted FakeLLM, no API calls."""

from __future__ import annotations

import pytest

from brain.boardroom import MAX_REBUTTAL_ROUNDS, BoardroomSession, slugify
from tests.fake_llm import FakeLLM


@pytest.fixture
def boardroom_env(config, hq, tmp_hq_root):
    """Seed the minimal HQ + prompt files a session needs."""
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter\nHonesty norm.", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives").mkdir(exist_ok=True)
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nLast updated: 2026-07-16\n\n"
        "## Tier\n\nTier 0 — Read-only\n\n## Status\n\nactive\n",
        encoding="utf-8",
    )
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    for name in ("boardroom_participant.md", "boardroom_moderator.md", "boardroom_synthesis.md"):
        (prompts / name).write_text(f"# {name}", encoding="utf-8")
    return config, hq


def make_session(config, hq, llm, topic="Launch in September vs November?",
                 inputs=None, printed=None):
    inputs = inputs or []
    it = iter(inputs)
    return BoardroomSession(
        llm, config, hq, topic,
        input_fn=lambda prompt: next(it),
        print_fn=(printed.append if printed is not None else lambda s: None),
    )


class TestSlugify:
    def test_basic(self):
        assert slugify("September soft launch vs November!") == "september-soft-launch-vs-november"

    def test_truncates_at_max_len(self):
        assert len(slugify("x" * 100)) <= 40

    def test_empty_topic_falls_back(self):
        assert slugify("!!!") == "topic"


class TestConvene:
    def test_triage_convene_parses_departments(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["CONVENE: market_intel, creative"])
        session = make_session(config, hq, llm)
        assert session.convene() is True
        assert [p.department for p in session.participants] == ["market_intel", "creative"]
        # dormant creative is advisory; active market_intel is not
        assert session.participants[0].advisory is False
        assert session.participants[1].advisory is True

    def test_triage_decline_returns_false(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["DECLINE: brain ask can answer this alone"])
        printed = []
        session = make_session(config, hq, llm, printed=printed)
        assert session.convene() is False
        assert any("declines" in p for p in printed)
        assert any("brain ask" in p for p in printed)

    def test_malformed_triage_falls_back_to_active_departments(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["I think we should probably talk about it?"])
        session = make_session(config, hq, llm)
        assert session.convene() is True
        # Only market_intel is active in the fixture config
        assert [p.department for p in session.participants] == ["market_intel"]

    def test_explicit_depts_skips_triage(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=[])  # no triage call allowed
        session = make_session(config, hq, llm)
        assert session.convene(override_depts=["market_intel"]) is True
        assert llm.calls == []

    def test_unknown_override_dept_rejected(self, boardroom_env):
        config, hq = boardroom_env
        session = make_session(config, hq, FakeLLM())
        assert session.convene(override_depts=["nonsense"]) is False

    def test_all_flag_convenes_everyone(self, boardroom_env):
        config, hq = boardroom_env
        session = make_session(config, hq, FakeLLM())
        assert session.convene(all_departments=True) is True
        assert len(session.participants) == len(config.departments)


class TestBlindness:
    def test_positions_round_is_blind(self, boardroom_env):
        """The structural honesty norm: position-round user messages contain
        only topic + instruction — no other positions, no CEO text."""
        config, hq = boardroom_env
        llm = FakeLLM(responses=["MI position: go early", "CR position: wait"])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel", "creative"])
        session.run_positions()

        assert len(llm.calls) == 2
        second_call = llm.calls[1].user_message
        assert "go early" not in second_call          # first position not leaked
        assert "CEO" not in second_call               # no CEO text exists yet
        assert "ROUND: positions" in second_call

    def test_advisory_participant_has_no_directive_context(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["advisory position"])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["creative"])  # dormant
        session.run_positions()

        dynamic_block = llm.calls[0].system_blocks[1]["text"]
        assert "DORMANT" in dynamic_block
        assert "directive" not in dynamic_block.lower() or "no directive" in dynamic_block.lower()

    def test_active_participant_gets_directive_and_reports(self, boardroom_env, tmp_hq_root):
        config, hq = boardroom_env
        week = hq.current_week_key()
        (tmp_hq_root / "reports" / "market_intel").mkdir(parents=True, exist_ok=True)
        (tmp_hq_root / "reports" / "market_intel" / f"{week}.md").write_text(
            "# Report\nCompetitors circling.", encoding="utf-8"
        )
        llm = FakeLLM(responses=["position"])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel"])
        session.run_positions()

        dynamic_block = llm.calls[0].system_blocks[1]["text"]
        assert "Directive: Market Intel" in dynamic_block
        assert "Competitors circling" in dynamic_block


class TestRebuttals:
    def test_rebuttal_cap_enforced_even_if_moderator_says_yes(self, boardroom_env):
        config, hq = boardroom_env
        # 2 participants: positions(2) + rebuttal1(2) + call_question(1, says yes)
        # + rebuttal2(2) — then HARD STOP, no second call_question.
        llm = FakeLLM(responses=[
            "p1", "p2",                 # positions
            "r1a", "r1b",               # rebuttal 1
            "SECOND_ROUND: yes",        # moderator wants more
            "r2a", "r2b",               # rebuttal 2 (the cap)
        ])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel", "creative"])
        session.run_positions()
        session.run_rebuttals()
        assert len(llm.calls) == 7
        rounds = {e.round for e in session.transcript}
        assert "rebuttal-1" in rounds and "rebuttal-2" in rounds
        assert MAX_REBUTTAL_ROUNDS == 2

    def test_moderator_no_ends_after_one_round(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["p1", "r1a", "SECOND_ROUND: no"])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel"])
        session.run_positions()
        session.run_rebuttals()
        assert not any(e.round == "rebuttal-2" for e in session.transcript)

    def test_rebuttal_sees_prior_transcript(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["my blind position", "my rebuttal", "SECOND_ROUND: no"])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel"])
        session.run_positions()
        session.run_rebuttals()
        assert "my blind position" in llm.calls[1].user_message


class TestCEOFloor:
    def test_at_dept_routes_to_participant_and_interjection_none(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["participant answer", "NONE"])
        session = make_session(
            config, hq, llm,
            inputs=["@market_intel what changes your mind?", "done"],
        )
        session.convene(override_depts=["market_intel"])
        session.run_ceo_floor()

        assert "what changes your mind?" in llm.calls[0].user_message
        floor_entries = [e for e in session.transcript if e.round == "floor"]
        assert [e.speaker for e in floor_entries] == ["CEO", "market_intel"]

    def test_interjection_ruled_relevant_adds_one_reply(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["mi answer", "INTERJECT: creative", "creative interjection"])
        session = make_session(
            config, hq, llm,
            inputs=["@market_intel go", "done"],
        )
        session.convene(override_depts=["market_intel", "creative"])
        session.run_ceo_floor()
        speakers = [e.speaker for e in session.transcript if e.round == "floor"]
        assert speakers == ["CEO", "market_intel", "creative"]

    def test_bare_text_goes_to_brain(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=["brain floor reply"])
        session = make_session(config, hq, llm, inputs=["what's your read?", "done"])
        session.convene(override_depts=["market_intel"])
        session.run_ceo_floor()
        assert "floor_discussion" in llm.calls[0].user_message
        assert any(e.speaker == "brain" for e in session.transcript)


class TestFinalize:
    RECORDS_OUTPUT = """## Decision Log Entries

### Launch in September as a founding-member drop
- Rationale: POD limits downside; identity risk gated on badge approval. Dissents: creative (badge not final)
- Decided by: CEO
- Affected departments: market_intel, creative

## Directive Updates

### market_intel

```markdown
# Directive: Market Intel

Last updated: 2026-07-16

## Tier

Tier 0 — Read-only

## Standing orders

Track launch-window competitors weekly.
```

## Ruling Summary

September drop adopted, gated on badge approval by Aug 15. Dissent: creative.
"""

    def test_finalize_writes_all_records(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=[self.RECORDS_OUTPUT])
        session = make_session(config, hq, llm)
        session.convene(override_depts=["market_intel"])
        session.transcript.append(
            __import__("brain.boardroom", fromlist=["TranscriptEntry"]).TranscriptEntry(
                "positions", "market_intel", "go early"
            )
        )
        summary = session.finalize("Adopted: September drop.")

        transcript_text = summary["transcript_path"].read_text(encoding="utf-8")
        assert "go early" in transcript_text
        assert "September drop adopted" in transcript_text

        decisions = hq.read_decisions()
        assert len(decisions) == 1
        assert "Dissents: creative" in decisions[0].rationale

        directive = hq.read_directive("market_intel")
        assert "Track launch-window competitors" in directive
        assert summary["directives_updated"] == ["market_intel"]

    TIER_SMUGGLE_OUTPUT = """## Decision Log Entries

### Some ruling
- Rationale: reasons. Dissents: none
- Decided by: CEO
- Affected departments: market_intel

## Directive Updates

### market_intel

```markdown
# Directive: Market Intel

Last updated: 2026-07-16

## Tier

Tier 2 — Act-within-bounds

## Status

active
```

## Ruling Summary

Done.
"""

    def test_smuggled_tier_change_requires_ratification_declined(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=[self.TIER_SMUGGLE_OUTPUT])
        printed = []
        session = make_session(config, hq, llm, inputs=["n"], printed=printed)
        session.convene(override_depts=["market_intel"])
        summary = session.finalize("Adopted.")

        assert summary["directives_updated"] == []
        assert any("did not ratify" in w for w in summary["warnings"])
        # Original directive untouched
        assert "Tier 2" not in hq.read_directive("market_intel")

    def test_smuggled_tier_change_ratified_writes_and_records(self, boardroom_env):
        config, hq = boardroom_env
        llm = FakeLLM(responses=[self.TIER_SMUGGLE_OUTPUT])
        session = make_session(config, hq, llm, inputs=["y"])
        session.convene(override_depts=["market_intel"])
        summary = session.finalize("Adopted.")

        assert summary["directives_updated"] == ["market_intel"]
        assert "Tier 2" in hq.read_directive("market_intel")
        # The explicit ratification is part of the permanent transcript
        transcript = summary["transcript_path"].read_text(encoding="utf-8")
        assert "Explicitly ratified" in transcript

    def test_transcript_collision_gets_suffix(self, boardroom_env):
        config, hq = boardroom_env
        week = hq.current_week_key()
        p1 = hq.write_boardroom_transcript(week, "same-topic", "first")
        p2 = hq.write_boardroom_transcript(week, "same-topic", "second")
        assert p1 != p2
        assert p2.name.endswith("-2.md")
