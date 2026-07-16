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


class FloorRequest(BaseModel):
    message: str


class RuleRequest(BaseModel):
    ruling: str
    # Answers to tier-ratification questions, keyed by department. The first
    # /rule call without answers returns needs_ratification; the UI asks the
    # CEO and re-posts with answers filled in.
    ratifications: dict[str, bool] = {}


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

        session = BoardroomSession(
            make_llm(), config, hq, topic,
            input_fn=lambda prompt: "",  # never used by dashboard flow
            print_fn=lambda s: None,
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
