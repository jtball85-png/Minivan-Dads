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
