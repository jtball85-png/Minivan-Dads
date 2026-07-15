"""Loads and validates brain/config.yaml into a BrainConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from brain.models import DepartmentConfig

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


@dataclass
class BrainConfig:
    model: str
    max_tokens: dict[str, int]
    effort: dict[str, str]
    hq_root: Path
    prompts_root: Path
    stale_directive_days: int
    decision_log_recent_n: int
    departments: dict[str, DepartmentConfig] = field(default_factory=dict)

    def department_names(self) -> list[str]:
        return list(self.departments.keys())


def load_config(path: Path | None = None, repo_root: Path | None = None) -> BrainConfig:
    """Load config.yaml. Paths for hq_root/prompts_root are resolved relative
    to repo_root (defaults to the current working directory) so the CLI
    works regardless of where it's invoked from within the repo."""
    config_path = path or DEFAULT_CONFIG_PATH
    root = repo_root or Path.cwd()

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    departments = {
        d["name"]: DepartmentConfig(
            name=d["name"],
            tier=d["tier"],
            status=d["status"],
            report_cadence=d["report_cadence"],
        )
        for d in raw["departments"]
    }

    return BrainConfig(
        model=raw["model"],
        max_tokens=raw["max_tokens"],
        effort=raw["effort"],
        hq_root=root / raw["paths"]["hq_root"],
        prompts_root=root / raw["paths"]["prompts_root"],
        stale_directive_days=raw["stale_directive_days"],
        decision_log_recent_n=raw["decision_log_recent_n"],
        departments=departments,
    )
