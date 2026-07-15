"""CLI entrypoint for the brain. `python -m brain <command>`."""

from __future__ import annotations

import argparse
import re
from datetime import date

from dotenv import load_dotenv

from brain.config import BrainConfig, load_config
from brain.hq import HQ
from brain.llm import LLM
from brain.models import DecisionEntry
from brain.prompts import build_system_blocks

DECISION_RECORD_RE = re.compile(
    r"^## Decision Record\s*\n"
    r"- Decision:\s*(?P<title>.+)\n"
    r"- Rationale:\s*(?P<rationale>.+)\n"
    r"- Decided by:\s*(?P<decided_by>.+)\n"
    r"- Affected departments:\s*(?P<departments>.+)",
    re.MULTILINE,
)


def cmd_status(hq: HQ) -> None:
    week = hq.current_week_key()
    statuses = hq.reports_status(week)

    print(f"=== Minivan Dads — Status ({week}) ===\n")
    print("Departments:")
    for dept, status in statuses.items():
        print(f"  {dept:<15} {status.value}")

    escalations = hq.read_escalation_queue()
    urgent = [e for e in escalations if e.urgency == "urgent"]
    normal = [e for e in escalations if e.urgency != "urgent"]

    print(f"\nOpen escalations: {len(escalations)} ({len(urgent)} urgent)")
    if urgent:
        print("  ** URGENT — no push alerts in Phase 1; this is surfaced only because you ran this command **")
        for e in urgent:
            print(f"  [URGENT] {e.id}: {e.summary}")
    for e in normal:
        print(f"  {e.id}: {e.summary}")

    last_meeting = hq.last_meeting_date()
    if last_meeting:
        days_since = (date.today() - last_meeting).days
        print(f"\nLast board meeting: {last_meeting.isoformat()} ({days_since} days ago)")
    else:
        print("\nLast board meeting: none yet")

    stale = hq.stale_directives(days=hq.config.stale_directive_days)
    if stale:
        print(f"\nStale directives (>{hq.config.stale_directive_days} days): {', '.join(stale)}")
    else:
        print("\nStale directives: none")


def cmd_ask(hq: HQ, llm: LLM, config: BrainConfig, question: str) -> None:
    system_blocks = build_system_blocks(config, hq, "ask.md")
    answer = llm.call(system_blocks, question, max_tokens=config.max_tokens["ask"])
    print(answer)

    m = DECISION_RECORD_RE.search(answer)
    if m:
        confirm = input("\nLog this as a decision? [y/N] ").strip().lower()
        if confirm == "y":
            departments_raw = m.group("departments").strip()
            departments = (
                [d.strip() for d in departments_raw.split(",") if d.strip() and d.strip().lower() != "none"]
                if departments_raw
                else []
            )
            hq.append_decision(
                DecisionEntry(
                    date=date.today(),
                    title=m.group("title").strip(),
                    rationale=m.group("rationale").strip(),
                    decided_by=m.group("decided_by").strip(),
                    departments=departments,
                )
            )
            print("Logged.")
        else:
            print("Not logged.")


def cli() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="brain", description="Minivan Dads COO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show the company dashboard")

    ask_parser = subparsers.add_parser("ask", help="Ask the brain a question")
    ask_parser.add_argument("question", help="The question to ask")

    args = parser.parse_args()

    config = load_config()
    hq = HQ(config)

    if args.command == "status":
        cmd_status(hq)
    elif args.command == "ask":
        llm = LLM(config)
        cmd_ask(hq, llm, config, args.question)


if __name__ == "__main__":
    cli()
