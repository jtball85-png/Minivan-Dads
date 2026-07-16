"""A scripted connector for executor tests. Records every call; can be armed
to raise on read_state or execute."""

from __future__ import annotations

from brain.actions.models import ActionType


class FakeConnector:
    def __init__(self, current_state: dict | None = None):
        self.current_state = current_state or {"current_value": 100.0}
        self.calls: list[tuple[str, str, dict]] = []  # (method, action_name, params/snapshot)
        self.raise_on_read = False
        self.raise_on_execute = False

    def read_state(self, action_type: ActionType, params: dict) -> dict:
        self.calls.append(("read_state", action_type.name, dict(params)))
        if self.raise_on_read:
            raise RuntimeError("read_state exploded")
        return dict(self.current_state)

    def execute(self, action_type: ActionType, params: dict) -> dict:
        self.calls.append(("execute", action_type.name, dict(params)))
        if self.raise_on_execute:
            raise RuntimeError("execute exploded")
        return {"ok": True}

    def restore(self, action_type: ActionType, snapshot: dict) -> dict:
        self.calls.append(("restore", action_type.name, dict(snapshot)))
        return {"restored": True}
