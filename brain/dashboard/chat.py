"""Chat surfaces for the CEO dashboard — the only dashboard module allowed
to touch brain.llm. app.py stays a pure read-only view; these routes are
registered separately by cmd_dashboard so the view works even when the model
is unavailable (no API key, offline).

SSE conventions: every event line is `data: <json>\n\n`. Text streams send
{"delta": "..."} events and finish with {"done": true, ...extras}.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from brain.config import BrainConfig
from brain.hq import HQ
from brain.models import DecisionEntry
from brain.prompts import build_system_blocks


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


class AskRequest(BaseModel):
    question: str


class LogDecisionRequest(BaseModel):
    title: str
    rationale: str
    decided_by: str = "CEO"
    departments: list[str] = []


class BoardroomOpenRequest(BaseModel):
    topic: str
    depts: list[str] | None = None
    all: bool = False
    # Share a department's latest report with the whole board as an exhibit
    # (the #discuss command). The report text is fetched server-side.
    exhibit_department: str | None = None


class FloorRequest(BaseModel):
    message: str


class RuleRequest(BaseModel):
    ruling: str
    # Answers to tier-ratification questions, keyed by department. The first
    # /rule call without answers returns needs_ratification; the UI asks the
    # CEO and re-posts with answers filled in.
    ratifications: dict[str, bool] = {}


class AgentRequest(BaseModel):
    department: str


class ConsultRequest(BaseModel):
    department: str
    message: str


class MeetingDiscussRequest(BaseModel):
    item_id: int
    text: str


class MeetingRulingRequest(BaseModel):
    item_id: int
    action: str  # approve | modify | reject | skip
    note: str = ""


class MeetingCloseRequest(BaseModel):
    ratifications: dict[str, bool] = {}


class DirectiveRequest(BaseModel):
    department: str
    changes: str


class DirectiveConfirmRequest(BaseModel):
    department: str


# The command bar's reference — names, syntax, and one-liners the UI renders
# for #help and for autocomplete hints.
COMMAND_HELP = [
    {"command": "#status", "syntax": "#status",
     "help": "Jump to the Dashboard tab and refresh the company glance."},
    {"command": "#ingest", "syntax": "#ingest",
     "help": "Read new reports and write this week's board-meeting agenda."},
    {"command": "#meeting", "syntax": "#meeting",
     "help": "Run the weekly board meeting right here, item by item."},
    {"command": "#boardroom", "syntax": "#boardroom <topic>",
     "help": "Convene a multi-agent debate on a topic (opens the Boardroom tab)."},
    {"command": "#agent", "syntax": "#agent <department>",
     "help": "Run a department agent's research loop now instead of waiting for Thursday."},
    {"command": "#discuss", "syntax": "#discuss <department> [topic]",
     "help": "Share that department's latest report with the whole board and open a debate on it."},
    {"command": "#directive", "syntax": "#directive <department> <changes in plain English>",
     "help": "Revise a department's standing orders; you confirm before it's written."},
    {"command": "#help", "syntax": "#help",
     "help": "Show this list."},
    {"command": "@department", "syntax": "@market_intel <question>",
     "help": "Ask one department head directly (a consult — no records written)."},
    {"command": "(plain text)", "syntax": "just type",
     "help": "Anything else is a question for the brain, full company context loaded."},
]


def register_chat_routes(app: FastAPI, config: BrainConfig, hq: HQ, make_llm) -> None:
    """`make_llm` is a zero-arg factory returning an object with
    stream()/call() — the real LLM in production, a fake in tests."""

    @app.post("/api/ask")
    def ask(body: AskRequest):
        from brain.main import DECISION_RECORD_RE

        question = body.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="Empty question")

        llm = make_llm()
        system_blocks = build_system_blocks(config, hq, "ask.md")

        def event_stream():
            chunks: list[str] = []
            for delta in llm.stream(system_blocks, question,
                                    max_tokens=config.max_tokens["ask"]):
                chunks.append(delta)
                yield _sse({"delta": delta})

            answer = "".join(chunks)
            record = None
            m = DECISION_RECORD_RE.search(answer)
            if m:
                departments_raw = m.group("departments").strip()
                record = {
                    "title": m.group("title").strip(),
                    "rationale": m.group("rationale").strip(),
                    "decided_by": m.group("decided_by").strip(),
                    "departments": [
                        d.strip() for d in departments_raw.split(",")
                        if d.strip() and d.strip().lower() != "none"
                    ],
                }
            yield _sse({"done": True, "decision_record": record})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/ask/log-decision")
    def log_decision(body: LogDecisionRequest):
        # The CEO clicked "Log it" in the UI — same confirm-then-log contract
        # as the CLI's [y/N] prompt.
        hq.append_decision(DecisionEntry(
            date=date.today(),
            title=body.title,
            rationale=body.rationale,
            decided_by=body.decided_by,
            departments=body.departments,
        ))
        return {"logged": True}

    # ------------------------------------------------------------------
    # Live boardroom. One debate at a time (single-CEO localhost app);
    # the in-flight session is the only state the dashboard ever holds,
    # and everything durable still lands in HQ at /rule.
    # ------------------------------------------------------------------
    state: dict = {"session": None, "prepared": None}

    def _session():
        if state["session"] is None:
            raise HTTPException(status_code=409, detail="No boardroom in progress — open a topic first.")
        return state["session"]

    @app.post("/api/boardroom/open")
    def boardroom_open(body: BoardroomOpenRequest):
        from brain.boardroom import BoardroomSession

        if state["session"] is not None:
            raise HTTPException(status_code=409,
                                detail="A debate is already in progress — rule on it or abandon it first.")
        topic = body.topic.strip()
        if not topic:
            raise HTTPException(status_code=422, detail="Empty topic")

        exhibit, exhibit_label = "", ""
        if body.exhibit_department:
            dept = body.exhibit_department
            if dept not in config.departments:
                raise HTTPException(status_code=404, detail=f"Unknown department: {dept}")
            week = hq.latest_report_week(dept)
            if not week:
                raise HTTPException(status_code=404,
                                    detail=f"{dept} has no report on file to discuss.")
            exhibit = hq.read_report(dept, week)
            exhibit_label = f"{dept}'s report ({week})"

        session = BoardroomSession(
            make_llm(), config, hq, topic,
            input_fn=lambda prompt: "",  # never used by dashboard flow
            print_fn=lambda s: None,
            exhibit=exhibit, exhibit_label=exhibit_label,
        )

        def event_stream():
            convened = session.convene(override_depts=body.depts,
                                       all_departments=body.all)
            if not convened:
                yield _sse({"done": True, "declined": True,
                            "reason": "The brain declined to convene — try brain ask for this one."})
                return
            state["session"] = session
            yield _sse({"participants": [
                {"department": p.department, "advisory": p.advisory}
                for p in session.participants
            ]})

            for entry in session.positions_stream():
                yield _sse({"round": entry.round, "speaker": entry.speaker, "text": entry.text})
            for entry in session.rebuttals_stream():
                yield _sse({"round": entry.round, "speaker": entry.speaker, "text": entry.text})

            yield _sse({"done": True, "floor_open": True})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/boardroom/floor")
    def boardroom_floor(body: FloorRequest):
        session = _session()
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="Empty message")

        def event_stream():
            for entry in session.floor_exchange(message):
                yield _sse({"round": entry.round, "speaker": entry.speaker, "text": entry.text})
            yield _sse({"done": True})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/boardroom/synthesize")
    def boardroom_synthesize():
        session = _session()

        def event_stream():
            for delta in session.synthesis_stream():
                yield _sse({"delta": delta})
            yield _sse({"done": True})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/boardroom/rule")
    def boardroom_rule(body: RuleRequest):
        session = _session()
        ruling = body.ruling.strip()
        if not ruling:
            raise HTTPException(status_code=422, detail="Empty ruling")

        # First call runs the records model and holds the bundle; if tier
        # ratifications are needed and unanswered, nothing is written and the
        # UI must re-post with answers. Second call reuses the bundle.
        if state["prepared"] is None:
            from brain.boardroom import TranscriptEntry
            session.transcript.append(TranscriptEntry("ruling", "CEO", ruling))
            state["prepared"] = session.prepare_records(ruling)

        prepared = state["prepared"]
        unanswered = [
            p for p in prepared["pending_ratifications"]
            if p["dept"] not in body.ratifications
        ]
        if unanswered:
            return {"needs_ratification": unanswered}

        summary = session.commit_records(
            prepared,
            ratify_fn=lambda dept, change: bool(body.ratifications.get(dept)),
        )
        state["session"] = None
        state["prepared"] = None
        return {
            "transcript_path": str(summary["transcript_path"]),
            "decisions": summary["decisions"],
            "directives_updated": summary["directives_updated"],
            "warnings": summary["warnings"],
        }

    @app.post("/api/boardroom/abandon")
    def boardroom_abandon():
        # Walk away without records — nothing was written to HQ yet.
        state["session"] = None
        state["prepared"] = None
        return {"abandoned": True}

    # ------------------------------------------------------------------
    # Command-bar endpoints: everything the CLI can do, from the browser.
    # ------------------------------------------------------------------

    @app.post("/api/command/ingest")
    def command_ingest():
        from brain.meeting import run_ingest

        def event_stream():
            yield _sse({"line": "Reading reports and synthesizing the agenda…"})
            summary = run_ingest(hq, llm=make_llm(), config=config,
                                 print_fn=lambda s: None)
            agenda_text = summary["path"].read_text(encoding="utf-8")
            yield _sse({
                "done": True,
                "path": str(summary["path"]),
                "decisions": summary["decisions"],
                "upgrades": summary["upgrades"],
                "reports_found": summary["reports_found"],
                # The CEO must SEE the agenda, not a receipt for it.
                "agenda": agenda_text,
            })

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/command/agent")
    def command_agent(body: AgentRequest):
        from brain.agent import run_agent

        def event_stream():
            lines: list[str] = []

            def capture(line):
                lines.append(str(line))

            code = run_agent(body.department, config, hq, make_llm(), print_fn=capture)
            for line in lines:
                yield _sse({"line": line})
            yield _sse({"done": True, "exit_code": code})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/consult")
    def consult(body: ConsultRequest):
        from brain.boardroom import participant_blocks

        dept = body.department
        dept_config = config.departments.get(dept)
        if dept_config is None:
            raise HTTPException(status_code=404, detail=f"Unknown department: {dept}")
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="Empty message")

        advisory = dept_config.status != "active"
        blocks = participant_blocks(config, hq, "consult.md", dept, advisory)
        llm = make_llm()

        def event_stream():
            for delta in llm.stream(blocks, f"The CEO asks you directly: {message}",
                                    max_tokens=config.max_tokens["boardroom_floor"]):
                yield _sse({"delta": delta})
            yield _sse({"done": True, "advisory": advisory})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # -- meeting flow (one at a time, like the boardroom) ----------------

    meeting_state: dict = {"session": None, "prepared": None}

    def _meeting():
        if meeting_state["session"] is None:
            raise HTTPException(status_code=409, detail="No meeting in progress — start one first.")
        return meeting_state["session"]

    @app.post("/api/meeting/start")
    def meeting_start():
        from brain.meeting import MeetingSession

        if meeting_state["session"] is not None:
            raise HTTPException(status_code=409,
                                detail="A meeting is already in progress — close or abandon it first.")
        session = MeetingSession(make_llm(), config, hq)
        try:
            items = session.load_agenda()
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        meeting_state["session"] = session

        # The briefing = everything the brain prepared BESIDES the decision
        # blocks (department syntheses, cross-department notes, escalation
        # triage). The CEO reads the evidence before ruling on conclusions.
        agenda = session.agenda
        cut = agenda.find("## Proposed Decisions")
        briefing = agenda[:cut].strip() if cut != -1 else agenda.strip()
        # Triage follows the decision blocks in the agenda format; fold it
        # into the briefing so the CEO sees the queue before ruling.
        triage_cut = agenda.find("## Escalation Triage")
        if triage_cut != -1 and triage_cut > cut:
            briefing += "\n\n" + agenda[triage_cut:].strip()

        return {
            "week": session.week,
            "briefing": briefing,
            "items": [
                {"id": i.id, "title": i.title, "block_text": i.block_text, "tag": i.tag}
                for i in items
            ],
        }

    @app.post("/api/meeting/discuss")
    def meeting_discuss(body: MeetingDiscussRequest):
        session = _meeting()

        def event_stream():
            reply = session.discuss(body.item_id, body.text)
            yield _sse({"reply": reply, "done": True})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/meeting/ruling")
    def meeting_ruling(body: MeetingRulingRequest):
        session = _meeting()
        try:
            session.record_ruling(body.item_id, body.action, body.note)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {"recorded": True}

    @app.post("/api/meeting/close")
    def meeting_close(body: MeetingCloseRequest):
        session = _meeting()

        if meeting_state["prepared"] is None:
            meeting_state["prepared"] = session.prepare_close()
        prepared = meeting_state["prepared"]

        unanswered = [
            p for p in prepared.get("pending_ratifications", [])
            if p["dept"] not in body.ratifications
        ]
        if unanswered and not prepared.get("missing_sections"):
            return {"needs_ratification": unanswered}

        summary = session.commit_close(
            prepared,
            ratify_fn=lambda dept, change: bool(body.ratifications.get(dept)),
        )
        meeting_state["session"] = None
        meeting_state["prepared"] = None
        return {
            "minutes_path": str(summary["minutes_path"]),
            "decisions": summary["decisions"],
            "directives_updated": summary["directives_updated"],
            "escalations_resolved": summary["escalations_resolved"],
            "warnings": summary["warnings"],
        }

    @app.post("/api/meeting/abandon")
    def meeting_abandon():
        meeting_state["session"] = None
        meeting_state["prepared"] = None
        return {"abandoned": True}

    # -- directive flow ---------------------------------------------------

    directive_state: dict = {"department": None, "draft": None}

    @app.post("/api/command/directive")
    def command_directive(body: DirectiveRequest):
        from brain.records import FENCED_BLOCK_RE

        dept = body.department
        if dept not in config.departments:
            raise HTTPException(status_code=404, detail=f"Unknown department: {dept}")
        changes = body.changes.strip()
        if not changes:
            raise HTTPException(status_code=422, detail="Describe the changes you want")

        try:
            current = hq.read_directive(dept)
        except FileNotFoundError:
            current = "(no directive on file yet)"

        user_message = (
            f"Department: {dept}\n\nCurrent directive:\n\n{current}\n\n"
            f"CEO's requested changes:\n\n{changes}\n\n"
            f"Today's date is {date.today().isoformat()}."
        )
        system_blocks = build_system_blocks(config, hq, "directive.md")
        response = make_llm().call(system_blocks, user_message,
                                   max_tokens=config.max_tokens["directive"])

        if "[REQUIRES BOARD DECISION]" in response:
            directive_state["department"] = None
            directive_state["draft"] = None
            return {"response": response, "board_decision_required": True, "writable": False}

        fence_m = FENCED_BLOCK_RE.search(response)
        if not fence_m:
            return {"response": response, "board_decision_required": False, "writable": False}

        directive_state["department"] = dept
        directive_state["draft"] = fence_m.group(1).strip() + "\n"
        return {"response": response, "board_decision_required": False, "writable": True}

    @app.post("/api/command/directive/confirm")
    def command_directive_confirm(body: DirectiveConfirmRequest):
        if directive_state["department"] != body.department or not directive_state["draft"]:
            raise HTTPException(status_code=409,
                                detail="No pending directive draft for that department — draft one first.")
        path = hq.write_directive(body.department, directive_state["draft"])
        directive_state["department"] = None
        directive_state["draft"] = None
        return {"written": str(path)}

    @app.get("/api/command/help")
    def command_help():
        return COMMAND_HELP
