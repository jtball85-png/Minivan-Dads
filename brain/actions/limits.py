"""Loaders for the two halves of agent authority:

- limits.yaml (human-owned, in brain/actions/): what is allowed AT ALL, and
  within what bounds. The machine never writes this file.
- hq/actions/capabilities.yaml (machine-owned): the earned mode per
  (agent, action type) on the capability ladder. The executor demotes here
  automatically after rollbacks; promotions are board decisions and each
  entry references its decision. A missing entry means DRY_RUN — the
  fail-safe default for every new capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from brain.actions.models import MODE_LADDER, ActionMode, ActionType

DEFAULT_LIMITS_PATH = Path(__file__).parent / "limits.yaml"


@dataclass
class AgentLimits:
    allowed_actions: list[str] = field(default_factory=list)
    action_bounds: dict[str, dict] = field(default_factory=dict)  # action name -> bounds
    daily_action_cap: int | None = None
    publish_window: str | None = None  # "HH:MM-HH:MM"


def load_limits(path: Path | None = None,
                registry: dict[str, ActionType] | None = None) -> dict[str, AgentLimits]:
    """Parse limits.yaml. Fails fast on any action name (in allowed_actions
    or bounds) that isn't in the registry — a typo in the safety file means
    refuse to start, never silently permit."""
    limits_path = path or DEFAULT_LIMITS_PATH
    if not limits_path.exists():
        return {}

    with open(limits_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    result: dict[str, AgentLimits] = {}
    for agent, spec in raw.items():
        allowed = spec.get("allowed_actions", []) or []
        bounds_raw = spec.get("bounds", {}) or {}

        action_bounds: dict[str, dict] = {}
        daily_cap: int | None = None
        publish_window: str | None = None

        for key, value in bounds_raw.items():
            if "." in key:  # per-action bound, keyed by action type name
                action_bounds[key] = value
            elif key.endswith("_per_day"):
                daily_cap = int(value)
            elif key == "publish_window":
                # "06:00-21:00 CEO timezone" -> keep just the HH:MM-HH:MM part
                publish_window = str(value).split()[0]
            else:
                raise ValueError(f"limits.yaml: unknown bound key {key!r} for agent {agent!r}")

        if registry is not None:
            for name in [*allowed, *action_bounds.keys()]:
                if name not in registry:
                    raise ValueError(
                        f"limits.yaml names unregistered action {name!r} (agent {agent!r}). "
                        f"Fix the typo or register the action — refusing to load."
                    )

        result[agent] = AgentLimits(
            allowed_actions=allowed,
            action_bounds=action_bounds,
            daily_action_cap=daily_cap,
            publish_window=publish_window,
        )
    return result


def load_capabilities(path: Path) -> dict[str, dict[str, ActionMode]]:
    """Parse hq/actions/capabilities.yaml. Missing file or missing entry =
    DRY_RUN (handled by the executor's .get() defaults, not here)."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    result: dict[str, dict[str, ActionMode]] = {}
    for agent, actions in raw.items():
        result[agent] = {}
        for action_name, entry in (actions or {}).items():
            mode_str = entry.get("mode", "dry_run") if isinstance(entry, dict) else str(entry)
            result[agent][action_name] = ActionMode(mode_str)
    return result


def demote(mode: ActionMode) -> ActionMode:
    """One rung down the ladder; DRY_RUN stays DRY_RUN."""
    idx = MODE_LADDER.index(mode)
    return MODE_LADDER[max(0, idx - 1)]


def write_capability(path: Path, agent: str, action_name: str,
                     mode: ActionMode, note: str) -> None:
    """Rewrite capabilities.yaml with one entry changed (atomic replace).
    This is the ONLY writer of the file; limits.yaml is never touched."""
    import os

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    raw.setdefault(agent, {})[action_name] = {"mode": mode.value, "note": note}

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# MACHINE-OWNED — maintained by the executor. Promotions are board\n")
        f.write("# decisions (each entry's note references one); demotions are automatic\n")
        f.write("# after rollbacks. Human bounds live in brain/actions/limits.yaml.\n")
        yaml.safe_dump(raw, f, sort_keys=True)
    os.replace(tmp, path)
