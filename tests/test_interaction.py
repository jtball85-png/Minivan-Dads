"""Tests for the free-text-everywhere interaction primitive and its
integration points (ruling rendering, parser completeness, root discovery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.config import find_repo_root
from brain.interaction import Exchange, prompt_with_freetext, render_exchanges
from brain.main import RULING_OPTIONS, build_parser
from brain.meeting import render_rulings as _render_rulings
from brain.models import MeetingRuling


def _scripted_input(responses: list[str]):
    it = iter(responses)

    def fake_input(prompt: str) -> str:
        return next(it)

    return fake_input


def _no_discuss(text, history):
    raise AssertionError("discuss should not have been called")


class TestPromptWithFreetext:
    def test_option_key_returns_canonical_value(self):
        result = prompt_with_freetext(
            "> ", RULING_OPTIONS, _no_discuss,
            input_fn=_scripted_input(["a"]), print_fn=lambda s: None,
        )
        assert result == "approve"

    def test_full_word_matches(self):
        result = prompt_with_freetext(
            "> ", RULING_OPTIONS, _no_discuss,
            input_fn=_scripted_input(["REJECT"]), print_fn=lambda s: None,
        )
        assert result == "reject"

    def test_whitespace_and_case_insensitive(self):
        result = prompt_with_freetext(
            "> ", RULING_OPTIONS, _no_discuss,
            input_fn=_scripted_input(["  M  "]), print_fn=lambda s: None,
        )
        assert result == "modify"

    def test_empty_input_reprompts_with_hint(self):
        printed = []
        result = prompt_with_freetext(
            "> ", RULING_OPTIONS, _no_discuss,
            input_fn=_scripted_input(["", "s"]), print_fn=printed.append,
        )
        assert result == "skip"
        assert any("pick an option" in p for p in printed)

    def test_free_text_routes_to_discuss_and_reprompts(self):
        calls = []

        def discuss(text, history):
            calls.append(text)
            return "counsel given"

        printed = []
        transcript: list[Exchange] = []
        result = prompt_with_freetext(
            "> ", RULING_OPTIONS, discuss, transcript=transcript,
            input_fn=_scripted_input(["what would finance say?", "a"]),
            print_fn=printed.append,
        )
        assert result == "approve"
        assert calls == ["what would finance say?"]
        assert [e.speaker for e in transcript] == ["CEO", "brain"]
        assert transcript[1].text == "counsel given"
        assert any("counsel given" in p for p in printed)

    def test_multiple_discussion_turns_accumulate(self):
        def discuss(text, history):
            return f"reply to: {text}"

        transcript: list[Exchange] = []
        prompt_with_freetext(
            "> ", RULING_OPTIONS, discuss, transcript=transcript,
            input_fn=_scripted_input(["first question", "second question", "r"]),
            print_fn=lambda s: None,
        )
        assert len(transcript) == 4
        assert transcript[0].text == "first question"
        assert transcript[2].text == "second question"
        # History passed to discuss includes the pending CEO message
        assert transcript[3].text == "reply to: second question"


class TestRenderHelpers:
    def test_render_exchanges_with_indent(self):
        out = render_exchanges(
            [Exchange("CEO", "why?"), Exchange("brain", "because.")], indent="  "
        )
        assert out == "  CEO: why?\n  brain: because."

    def test_render_rulings_plain(self):
        text = _render_rulings([MeetingRuling(item_title="Do X", action="approve")])
        assert text == "- Do X: APPROVE"

    def test_render_rulings_with_note_and_discussion(self):
        ruling = MeetingRuling(
            item_title="Do Y",
            action="modify",
            ceo_note="do it smaller",
            discussion=[Exchange("CEO", "is Y risky?"), Exchange("brain", "mildly.")],
        )
        text = _render_rulings([ruling])
        assert "- Do Y: MODIFY — CEO note: do it smaller" in text
        assert "Discussion during ruling:" in text
        assert "    CEO: is Y risky?" in text
        assert "    brain: mildly." in text


class TestBuildParser:
    def test_all_subcommands_present_with_descriptions(self):
        parser = build_parser()
        subparsers_action = next(
            a for a in parser._actions if isinstance(a, type(parser._subparsers._group_actions[0]))
        )
        choices = subparsers_action.choices
        for cmd in ("status", "ask", "ingest", "meeting", "directive"):
            assert cmd in choices
            assert choices[cmd].description, f"{cmd} has no description"

    def test_parses_status(self):
        args = build_parser().parse_args(["status"])
        assert args.command == "status"

    def test_parses_ask_with_question(self):
        args = build_parser().parse_args(["ask", "what's our voice?"])
        assert args.question == "what's our voice?"


class TestFindRepoRoot:
    def test_walks_up_from_nested_dir(self, tmp_path, monkeypatch):
        (tmp_path / "hq" / "charter").mkdir(parents=True)
        (tmp_path / "hq" / "charter" / "company.md").write_text("x", encoding="utf-8")
        nested = tmp_path / "brain" / "prompts"
        nested.mkdir(parents=True)
        monkeypatch.delenv("BRAIN_ROOT", raising=False)
        assert find_repo_root(start=nested) == tmp_path

    def test_env_var_wins(self, tmp_path, monkeypatch):
        (tmp_path / "hq" / "charter").mkdir(parents=True)
        (tmp_path / "hq" / "charter" / "company.md").write_text("x", encoding="utf-8")
        monkeypatch.setenv("BRAIN_ROOT", str(tmp_path))
        assert find_repo_root(start=Path("/")) == tmp_path

    def test_bad_env_var_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BRAIN_ROOT", str(tmp_path))  # no hq/ inside
        with pytest.raises(FileNotFoundError, match="BRAIN_ROOT"):
            find_repo_root()

    def test_not_in_repo_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BRAIN_ROOT", raising=False)
        with pytest.raises(FileNotFoundError, match="BRAIN_ROOT"):
            find_repo_root(start=tmp_path)
