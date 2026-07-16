import pytest

from brain.config import BrainConfig
from brain.hq import HQ
from brain.models import DepartmentConfig


@pytest.fixture
def tmp_hq_root(tmp_path):
    hq_root = tmp_path / "hq"
    (hq_root / "charter").mkdir(parents=True)
    (hq_root / "directives").mkdir()
    (hq_root / "reports").mkdir()
    (hq_root / "decisions").mkdir()
    (hq_root / "escalations").mkdir()
    (hq_root / "meetings" / "monthly").mkdir(parents=True)
    return hq_root


@pytest.fixture
def config(tmp_hq_root):
    departments = {
        "market_intel": DepartmentConfig(
            name="market_intel", tier=0, status="active", report_cadence="weekly"
        ),
        "creative": DepartmentConfig(
            name="creative", tier=0, status="dormant", report_cadence="weekly"
        ),
    }
    return BrainConfig(
        model="claude-sonnet-5",
        max_tokens={
            "ask": 4096, "ingest": 8192, "meeting": 8192, "directive": 4096,
            "discussion": 1024, "boardroom_position": 600,
            "boardroom_moderator": 800, "boardroom_floor": 1500,
            "boardroom_synthesis": 8192,
        },
        effort={"ask": "medium", "ingest": "high", "meeting": "high", "directive": "medium"},
        hq_root=tmp_hq_root,
        prompts_root=tmp_hq_root.parent / "prompts",
        stale_directive_days=30,
        decision_log_recent_n=20,
        departments=departments,
    )


@pytest.fixture
def hq(config):
    return HQ(config)
