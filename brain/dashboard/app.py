"""The CEO dashboard: a local, read-only web view over HQ files.

Design rules (boardroom/dashboard spec Part B):
- The dashboard is a VIEW plus (later) a chat surface. It holds no state of
  its own — every endpoint re-reads HQ per request, so anything visible here
  corresponds to a file in git.
- This module NEVER imports brain.llm (test-enforced). Chat surfaces
  (brain ask, live boardroom) attach in a later increment.
- Localhost only, no auth, v1.
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from brain.config import BrainConfig
from brain.hq import HQ

STATIC_DIR = Path(__file__).parent / "static"


def _directive_git_history(hq_root: Path, dept: str) -> list[dict]:
    """Read-only `git log` over a directive file; [] when git is unavailable
    or the tree isn't a repo — history is a nicety, never a failure."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%h|%ad|%s", "--date=short", "--",
             f"hq/directives/{dept}.md"],
            capture_output=True, text=True, timeout=10,
            cwd=hq_root.parent, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    history = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            history.append({"commit": parts[0], "date": parts[1], "message": parts[2]})
    return history


def create_app(config: BrainConfig, hq: HQ) -> FastAPI:
    app = FastAPI(title="Minivan Dads — CEO Console", docs_url=None, redoc_url=None)
    app.state.chat_error = "chat routes not registered"  # cleared by cmd_dashboard on success

    @app.get("/api/health")
    def health():
        """Lets the UI say plainly whether chat is up, instead of surfacing
        mystery 404s when it isn't."""
        error = app.state.chat_error
        return {"chat": error is None, "chat_error": error}

    @app.get("/api/overview")
    def overview():
        week = hq.current_week_key()
        statuses = hq.reports_status(week)
        escalations = hq.read_escalation_queue()
        decisions = hq.read_decisions(limit=10)
        last_meeting = hq.last_meeting_date()

        agenda_path = hq.root / "meetings" / f"{week}-agenda.md"
        agenda = agenda_path.read_text(encoding="utf-8") if agenda_path.exists() else None

        return {
            "week": week,
            "stats": {
                "open_escalations": len(escalations),
                "urgent_escalations": sum(1 for e in escalations if e.urgency == "urgent"),
                "reports_filed": sum(1 for s in statuses.values() if s.value == "filed"),
                "reports_expected": sum(1 for s in statuses.values() if s.value != "dormant"),
                "decisions_logged": len(hq.read_decisions(limit=10_000)),
                "stale_directives": len(hq.stale_directives(days=config.stale_directive_days)),
                "last_meeting": last_meeting.isoformat() if last_meeting else None,
                "days_since_meeting": (date.today() - last_meeting).days if last_meeting else None,
            },
            "escalations": [
                {"id": e.id, "urgency": e.urgency, "summary": e.summary,
                 "raised": e.raised.isoformat(), "raised_by": e.raised_by}
                for e in sorted(escalations, key=lambda e: e.urgency != "urgent")
            ],
            "recent_decisions": [
                {"date": d.date.isoformat(), "title": d.title,
                 "decided_by": d.decided_by, "departments": d.departments}
                for d in reversed(decisions)
            ],
            "this_week_agenda": agenda,
        }

    @app.get("/api/departments")
    def departments():
        return [
            {
                "name": name,
                "tier": dept.tier,
                "status": dept.status,
                "report_cadence": dept.report_cadence,
                "last_report_week": hq.latest_report_week(name),
            }
            for name, dept in config.departments.items()
        ]

    @app.get("/api/departments/{name}")
    def department_detail(name: str):
        if name not in config.departments:
            raise HTTPException(status_code=404, detail=f"Unknown department: {name}")
        dept = config.departments[name]
        try:
            directive = hq.read_directive(name)
        except FileNotFoundError:
            directive = None
        latest_week = hq.latest_report_week(name)
        report = hq.read_report(name, latest_week) if latest_week else None
        actions = [
            {"id": r.id, "timestamp": r.timestamp, "action_type": r.action_type,
             "mode": r.mode, "result": r.result, "reasons": r.reasons}
            for r in hq.read_actions() if r.agent == name
        ]
        return {
            "name": name,
            "tier": dept.tier,
            "status": dept.status,
            "directive": directive,
            "latest_report_week": latest_week,
            "latest_report": report,
            "actions": actions,
            "directive_history": _directive_git_history(hq.root, name),
        }

    @app.get("/api/boardroom")
    def boardroom_list():
        meetings_dir = hq.root / "meetings"
        if not meetings_dir.exists():
            return []
        files = sorted(meetings_dir.glob("*-boardroom-*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return [
            {"filename": p.name,
             "week": p.name.split("-boardroom-")[0],
             "slug": p.name.split("-boardroom-")[1].removesuffix(".md")}
            for p in files
        ]

    @app.get("/api/boardroom/{filename}")
    def boardroom_transcript(filename: str):
        meetings_dir = hq.root / "meetings"
        # Path traversal guard: the file must be one of the glob results.
        valid = {p.name for p in meetings_dir.glob("*-boardroom-*.md")} if meetings_dir.exists() else set()
        if filename not in valid:
            raise HTTPException(status_code=404, detail="No such transcript")
        return {"filename": filename,
                "content": (meetings_dir / filename).read_text(encoding="utf-8")}

    @app.get("/api/commands")
    def commands():
        # Generated from the CLI's own parser, so this can never drift.
        from brain.main import build_parser

        parser = build_parser()
        subparsers_action = parser._subparsers._group_actions[0]
        return [
            {
                "name": name,
                "help": sub.format_usage().strip(),
                "description": sub.description or "",
                "full_help": sub.format_help(),
            }
            for name, sub in subparsers_action.choices.items()
        ]

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
