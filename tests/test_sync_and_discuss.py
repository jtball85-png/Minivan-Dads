"""Tests for the cloud-sync endpoints, boardroom exhibits (#discuss), and
minutes collision protection."""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from brain.boardroom import BoardroomSession
from brain.dashboard.app import create_app
from brain.dashboard.chat import register_chat_routes
from tests.fake_llm import FakeLLM


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def synced_repos(tmp_path, config, tmp_hq_root):
    """A bare 'origin' and a working clone whose hq/ is the fixture's HQ.
    Returns (clone_root, origin_path). config.hq_root is repointed into the
    clone so the app's git ops (cwd=hq.root.parent) hit a real repo."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    git("init", "--bare", "--initial-branch=main", str(origin), cwd=tmp_path)

    clone = tmp_path / "clone"
    git("clone", str(origin), str(clone), cwd=tmp_path)
    git("config", "user.email", "t@t", cwd=clone)
    git("config", "user.name", "t", cwd=clone)
    (clone / "hq" / "reports" / "market_intel").mkdir(parents=True)
    (clone / "hq" / "charter").mkdir(parents=True)
    (clone / "hq" / "charter" / "company.md").write_text("# Charter", encoding="utf-8")
    (clone / "README.md").write_text("x", encoding="utf-8")
    git("add", "-A", cwd=clone)
    git("commit", "-m", "init", cwd=clone)
    git("push", "origin", "main", cwd=clone)

    config.hq_root = clone / "hq"
    return clone, origin


def push_cloud_report(tmp_path, origin, week="2026-W99"):
    """Simulate the scheduled run: a second clone pushes a new report."""
    cloud = tmp_path / "cloud"
    git("clone", str(origin), str(cloud), cwd=tmp_path)
    git("config", "user.email", "agent@x", cwd=cloud)
    git("config", "user.name", "agent", cwd=cloud)
    report = cloud / "hq" / "reports" / "market_intel" / f"{week}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Report\nCloud finding.", encoding="utf-8")
    git("add", "-A", cwd=cloud)
    git("commit", "-m", f"Market Intel weekly report ({week})", cwd=cloud)
    git("push", "origin", "main", cwd=cloud)


class TestSync:
    def test_in_sync_reports_zero_behind(self, tmp_path, config, hq, synced_repos):
        from brain.hq import HQ
        client = TestClient(create_app(config, HQ(config)))
        data = client.get("/api/sync/check").json()
        assert data["ok"] is True
        assert data["behind"] == 0

    def test_detects_cloud_report_and_pulls(self, tmp_path, config, synced_repos):
        from brain.hq import HQ
        clone, origin = synced_repos
        push_cloud_report(tmp_path, origin)

        client = TestClient(create_app(config, HQ(config)))
        data = client.get("/api/sync/check").json()
        assert data["behind"] == 1
        assert any("2026-W99" in f for f in data["new_reports"])
        assert "Market Intel weekly report" in data["latest"]

        pulled = client.post("/api/sync/pull").json()
        assert pulled["ok"] is True
        assert (clone / "hq" / "reports" / "market_intel" / "2026-W99.md").exists()
        assert client.get("/api/sync/check").json()["behind"] == 0

    def test_check_degrades_without_remote(self, config, hq, tmp_hq_root):
        # tmp HQ isn't a git repo at all — endpoint must not 500.
        client = TestClient(create_app(config, hq))
        data = client.get("/api/sync/check").json()
        assert data["ok"] is False


class TestExhibit:
    def test_topic_block_includes_exhibit(self, config, hq):
        session = BoardroomSession(FakeLLM(), config, hq, "What next?",
                                   exhibit="THE REPORT BODY",
                                   exhibit_label="market_intel's report (2026-W29)")
        block = session._topic_block()
        assert "What next?" in block
        assert "THE REPORT BODY" in block
        assert "market_intel's report" in block

    def test_positions_round_carries_exhibit(self, config, hq, tmp_hq_root):
        (tmp_hq_root / "charter" / "company.md").write_text("# C", encoding="utf-8")
        (tmp_hq_root / "charter" / "tiers.md").write_text("# T", encoding="utf-8")
        prompts = config.prompts_root
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "boardroom_participant.md").write_text("# p", encoding="utf-8")

        llm = FakeLLM(responses=["position"])
        session = BoardroomSession(llm, config, hq, "Topic?",
                                   print_fn=lambda s: None,
                                   exhibit="EXHIBIT TEXT", exhibit_label="report")
        session.convene(override_depts=["creative"])
        session.run_positions()
        assert "EXHIBIT TEXT" in llm.calls[0].user_message

    def test_open_endpoint_fetches_report_as_exhibit(self, config, hq, tmp_hq_root):
        (tmp_hq_root / "charter" / "company.md").write_text("# C", encoding="utf-8")
        (tmp_hq_root / "charter" / "tiers.md").write_text("# T", encoding="utf-8")
        prompts = config.prompts_root
        prompts.mkdir(parents=True, exist_ok=True)
        for name in ("boardroom_participant.md", "boardroom_moderator.md"):
            (prompts / name).write_text(f"# {name}", encoding="utf-8")
        (tmp_hq_root / "directives").mkdir(exist_ok=True)
        (tmp_hq_root / "directives" / "market_intel.md").write_text("# D", encoding="utf-8")
        week = hq.current_week_key()
        hq.write_report("market_intel", week, "# R\nDISCUSSABLE FINDING")

        llm = FakeLLM(responses=["p1", "r1", "SECOND_ROUND: no"])
        app = create_app(config, hq)
        register_chat_routes(app, config, hq, make_llm=lambda command=None: llm)
        client = TestClient(app)
        response = client.post("/api/boardroom/open", json={
            "topic": "Discuss the report",
            "depts": ["market_intel"],
            "exhibit_department": "market_intel",
        })
        assert response.status_code == 200
        assert "DISCUSSABLE FINDING" in llm.calls[0].user_message
        client.post("/api/boardroom/abandon")

    def test_open_404s_when_no_report_to_discuss(self, config, hq, tmp_hq_root):
        app = create_app(config, hq)
        register_chat_routes(app, config, hq, make_llm=lambda command=None: FakeLLM())
        client = TestClient(app)
        response = client.post("/api/boardroom/open", json={
            "topic": "Discuss", "exhibit_department": "creative",
        })
        assert response.status_code == 404


class TestMinutesCollision:
    def test_second_meeting_same_week_gets_suffix(self, hq):
        p1 = hq.write_minutes("2026-W30", "first meeting")
        p2 = hq.write_minutes("2026-W30", "second meeting")
        assert p1.name == "2026-W30-minutes.md"
        assert p2.name == "2026-W30-minutes-2.md"
        assert p1.read_text(encoding="utf-8") == "first meeting"
