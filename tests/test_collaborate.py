"""Inter-department collaboration (#collab) — session + endpoint, FakeLLM."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from brain.collaborate import CollaborationSession
from brain.dashboard.app import create_app
from brain.dashboard.chat import register_chat_routes
from tests.fake_llm import FakeLLM


class StreamingFakeLLM(FakeLLM):
    def stream(self, system_blocks, user_message, max_tokens=1024):
        text = self.call(system_blocks, user_message, max_tokens)
        for i in range(0, len(text), 8):
            yield text[i:i + 8]


def parse_sse(text):
    return [json.loads(line[6:]) for line in text.split("\n\n") if line.startswith("data: ")]


@pytest.fixture
def collab_env(config, hq, tmp_hq_root):
    (tmp_hq_root / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (tmp_hq_root / "charter" / "tiers.md").write_text("# Tiers", encoding="utf-8")
    (tmp_hq_root / "directives" / "market_intel.md").write_text(
        "# Directive: Market Intel\n\nWatch the niche.\n", encoding="utf-8"
    )
    prompts = config.prompts_root
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "collaborate.md").write_text("# collaborate", encoding="utf-8")
    (prompts / "boardroom_participant.md").write_text("# p", encoding="utf-8")
    return config, hq


class TestCollaborationSession:
    def test_contributions_are_sequential_and_see_prior_work(self, collab_env):
        config, hq = collab_env
        llm = StreamingFakeLLM(responses=["MI: found 8 names", "CR: ranked them"])
        session = CollaborationSession(llm, config, hq, "name the brand",
                                       ["market_intel", "creative"])
        list(session.contribute_stream())

        assert [c.department for c in session.contributions] == ["market_intel", "creative"]
        # Creative's call must contain Market Intel's contribution
        creative_call = llm.calls[1].user_message
        assert "MI: found 8 names" in creative_call
        # Market Intel's call must NOT contain Creative's (it went first)
        assert "ranked them" not in llm.calls[0].user_message

    def test_dormant_department_contributes_advisorily(self, collab_env):
        config, hq = collab_env  # creative is dormant in the fixture config
        llm = StreamingFakeLLM(responses=["MI part", "CR part"])
        session = CollaborationSession(llm, config, hq, "task", ["market_intel", "creative"])
        list(session.contribute_stream())
        creative_dynamic = llm.calls[1].system_blocks[1]["text"]
        assert "DORMANT" in creative_dynamic  # advisory, charter-only

    def test_run_saves_combined_deliverable_no_decisions_no_directive_change(self, collab_env):
        config, hq = collab_env
        before_directive = hq.read_directive("market_intel")
        llm = StreamingFakeLLM(responses=["MI part", "CR part", "THE MERGED DELIVERABLE"])
        session = CollaborationSession(llm, config, hq, "name the brand",
                                       ["market_intel", "creative"])
        result = session.run()

        content = result["path"].read_text(encoding="utf-8")
        assert "MI part" in content and "CR part" in content
        assert "THE MERGED DELIVERABLE" in content
        assert "Combined deliverable" in content
        # Collaboration is a work-product, NOT a decision or an order:
        assert hq.read_decisions() == []
        assert hq.read_directive("market_intel") == before_directive

    def test_save_collision_suffix(self, collab_env):
        config, hq = collab_env
        week = hq.current_week_key()
        p1 = hq.write_collaboration(week, "same", "one")
        p2 = hq.write_collaboration(week, "same", "two")
        assert p1 != p2 and p2.name.endswith("-2.md")


class TestCollaborateEndpoint:
    def _client(self, config, hq, responses):
        llm = StreamingFakeLLM(responses=responses)
        app = create_app(config, hq)
        register_chat_routes(app, config, hq, make_llm=lambda command=None: llm)
        return TestClient(app), llm

    def test_streams_contributions_then_synthesis_then_saves(self, collab_env):
        config, hq = collab_env
        client, _ = self._client(config, hq, ["MI part", "CR part", "merged"])
        response = client.post("/api/collaborate", json={
            "departments": ["market_intel", "creative"],
            "task": "produce a ranked name shortlist",
        })
        assert response.status_code == 200
        events = parse_sse(response.text)
        depts = [e["department"] for e in events if "department" in e]
        assert depts == ["market_intel", "creative"]
        synth = "".join(e.get("delta", "") for e in events)
        assert "merged" in synth
        assert events[-1]["done"] is True
        assert "collaborations" in events[-1]["path"]

    def test_requires_two_known_departments(self, collab_env):
        config, hq = collab_env
        client, _ = self._client(config, hq, [])
        assert client.post("/api/collaborate", json={
            "departments": ["market_intel"], "task": "x"}).status_code == 422
        assert client.post("/api/collaborate", json={
            "departments": ["market_intel", "nobody"], "task": "x"}).status_code == 422

    def test_empty_task_422(self, collab_env):
        config, hq = collab_env
        client, _ = self._client(config, hq, [])
        assert client.post("/api/collaborate", json={
            "departments": ["market_intel", "creative"], "task": "  "}).status_code == 422
