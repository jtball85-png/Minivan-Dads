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
from brain.pricing import summarize_usage

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

    def _run_git(*args: str, timeout: int = 30):
        return subprocess.run(
            ["git", *args], capture_output=True, text=True,
            timeout=timeout, cwd=hq.root.parent,
        )

    @app.get("/api/sync/check")
    def sync_check():
        """Has the cloud (scheduled agent runs) committed work we don't have
        locally? Powers the 'new report arrived' banner."""
        try:
            fetch = _run_git("fetch", "origin", timeout=45)
            if fetch.returncode != 0:
                return {"ok": False, "error": fetch.stderr.strip()[:300]}
            behind_raw = _run_git("rev-list", "--count", "HEAD..origin/main").stdout.strip()
            behind = int(behind_raw or 0)
            if behind == 0:
                return {"ok": True, "behind": 0, "new_reports": [], "latest": None}
            changed = _run_git("diff", "--name-only", "HEAD", "origin/main").stdout.splitlines()
            new_reports = [f for f in changed if f.startswith("hq/reports/")]
            latest = _run_git("log", "origin/main", "-1", "--format=%s").stdout.strip()
            return {"ok": True, "behind": behind, "new_reports": new_reports, "latest": latest}
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            return {"ok": False, "error": str(e)[:300]}

    @app.post("/api/sync/pull")
    def sync_pull():
        """Bring cloud-committed work into the local HQ (fast-forward only —
        never rewrites local history)."""
        result = _run_git("pull", "--ff-only", timeout=60)
        return {
            "ok": result.returncode == 0,
            "output": (result.stdout + result.stderr).strip()[-500:],
        }

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

    @app.get("/api/attention")
    def attention():
        """The 'what needs me today' list — everything genuinely waiting on a
        CEO decision, prioritized, each with a one-click action. Read-only,
        no model call. Priority 0 = urgent, higher = softer."""
        week = hq.current_week_key()
        escalations = hq.read_escalation_queue()
        urgent = [e for e in escalations if e.urgency == "urgent"]

        agenda_path = hq.root / "meetings" / f"{week}-agenda.md"
        minutes_path = hq.root / "meetings" / f"{week}-minutes.md"
        agenda_exists = agenda_path.exists()
        agenda_text = agenda_path.read_text(encoding="utf-8") if agenda_exists else ""

        # An agenda that predates a currently-open escalation is stale — it
        # can't be resolved at a meeting it never mentioned. So "fresh" means:
        # it exists and every open escalation id appears in it.
        agenda_covers = all(e.id in agenda_text for e in escalations)
        last_meeting = hq.last_meeting_date()
        since = hq.week_key_for_date(last_meeting) if last_meeting else "1970-W01"
        has_new_reports = any(entries for entries in hq.discover_reports(since).values())
        # A meeting is "current" only if its minutes are at least as new as the
        # agenda — a rebuilt agenda means the last meeting is stale.
        meeting_current = (
            minutes_path.exists() and agenda_exists
            and minutes_path.stat().st_mtime >= agenda_path.stat().st_mtime
        )

        items: list[dict] = []

        for e in urgent:
            items.append({
                "kind": "urgent_escalation", "priority": 0,
                "title": f"Urgent — {e.summary}",
                "detail": f"{e.id} · raised by {e.raised_by}",
                "action_label": "Ask the brain",
                "action_command": f"What should I do about {e.id}: {e.summary}",
            })

        # Exactly one meeting-state action, driven by what actually needs doing.
        if (escalations or has_new_reports) and (not agenda_exists or not agenda_covers):
            reasons = []
            if escalations:
                reasons.append(f"{len(escalations)} open item(s)")
            if has_new_reports and not agenda_exists:
                reasons.append("new reports")
            items.append({
                "kind": "build_agenda", "priority": 1,
                "title": ("Reports and open items are in — build this week's agenda"
                          if not agenda_exists else
                          "New items since the agenda was built — refresh it"),
                "detail": ", ".join(reasons) + " → synthesize the agenda, then hold the meeting",
                "action_label": "Build the agenda" if not agenda_exists else "Refresh the agenda",
                "action_command": "#ingest",
            })
        elif agenda_exists and agenda_covers and not meeting_current:
            items.append({
                "kind": "hold_meeting", "priority": 1,
                "title": "This week's agenda is ready — hold the board meeting",
                "detail": f"agenda for {week} covers the open items; no meeting held on it yet",
                "action_label": "Hold the meeting", "action_command": "#meeting",
            })

        stale = hq.stale_directives(days=config.stale_directive_days)
        if stale:
            items.append({
                "kind": "stale_directives", "priority": 3,
                "title": f"{len(stale)} directive(s) haven't been updated in a while",
                "detail": ", ".join(stale),
                "action_label": None, "action_command": None,
            })

        items.sort(key=lambda x: x["priority"])
        return {"items": items, "all_clear": not items}

    @app.get("/api/costs")
    def costs():
        """Cost visibility, read-only: this week's burn plus a typical
        cost per action, computed from actual logged usage (never a
        model call itself — 'looking is free')."""
        week_start = date.fromisocalendar(*date.today().isocalendar()[:2], 1)
        this_week = summarize_usage(hq.read_llm_usage(since=week_start))
        all_time = summarize_usage(hq.read_llm_usage())
        return {
            "week_start": week_start.isoformat(),
            "this_week": this_week,
            "all_time_cost": all_time["total_cost"],
            "typical_by_command": [
                {**entry, "avg_cost": entry["cost"] / entry["calls"]}
                for entry in all_time["by_command"]
            ],
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
