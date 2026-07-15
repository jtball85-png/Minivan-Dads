"""CLI entrypoint for the brain. `python -m brain <command>`."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from dotenv import load_dotenv

# Windows consoles often default to cp1252, which can't print the em-dashes
# and math symbols that show up in LLM-written agendas. Force UTF-8 rather
# than crashing mid-meeting on the first fancy character.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from brain.config import BrainConfig, load_config
from brain.governance import DECISION_HEADING_RE, apply_governance
from brain.hq import HQ
from brain.llm import LLM
from brain.models import DecisionEntry, MeetingRuling
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


def cmd_ingest(hq: HQ, llm: LLM, config: BrainConfig) -> None:
    week = hq.current_week_key()
    last_meeting = hq.last_meeting_date()
    since_week = hq.week_key_for_date(last_meeting) if last_meeting else "1970-W01"

    reports = hq.discover_reports(since_week)
    filed = {dept: entries for dept, entries in reports.items() if entries}
    print(f"Reports found since {since_week}: "
          + (", ".join(f"{d} ({len(e)})" for d, e in filed.items()) if filed else "none"))

    system_blocks = build_system_blocks(config, hq, "ingest.md")
    trigger = (
        f"Prepare the board meeting agenda for {week}. "
        f"Reports discovered since the last meeting are already in your context."
    )
    raw_agenda = llm.call(system_blocks, trigger, max_tokens=config.max_tokens["ingest"])

    corrected_agenda, enforced = apply_governance(raw_agenda)
    upgrades = [e for e in enforced if e.upgraded]

    path = hq.write_agenda(week, corrected_agenda)

    print(f"\nAgenda written: {path}")
    print(f"Proposed decisions: {len(enforced)}")
    if upgrades:
        print(f"Governance upgrades to [CEO REQUIRED]: {len(upgrades)}")
        for e in upgrades:
            print(f"  - {e.title}: {'; '.join(e.reasons)}")


MEETING_OUTPUT_SECTIONS = ["Minutes", "Decision Log Entries", "Directive Updates", "Resolved Escalations"]
# Split ONLY on the four known section headings — directive content inside
# the output legitimately contains its own ## headings (## Tier, ## Mandate)
# and must not break the split.
MEETING_SECTION_RE = re.compile(
    r"^## (Minutes|Decision Log Entries|Directive Updates|Resolved Escalations)\s*$", re.MULTILINE
)
LOG_ENTRY_HEADING_RE = re.compile(r"^### (.+)$", re.MULTILINE)
RESOLVED_LINE_RE = re.compile(r"^(ESC-\d+):\s*(.+)$", re.MULTILINE)
FENCED_BLOCK_RE = re.compile(r"```(?:markdown|md)?\s*\n(.*?)```", re.DOTALL)


def _split_sections(markdown: str, heading_re: re.Pattern) -> dict[str, str]:
    """Split markdown into {heading: body} on a heading regex."""
    matches = list(heading_re.finditer(markdown))
    sections = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections[m.group(1).strip()] = markdown[start:end].strip()
    return sections


def _collect_rulings(agenda: str) -> list[MeetingRuling]:
    """Walk the agenda's decision blocks interactively, one at a time."""
    blocks = list(DECISION_HEADING_RE.finditer(agenda))
    if not blocks:
        print("No proposed decisions found in the agenda.")
        return []

    rulings: list[MeetingRuling] = []
    for i, m in enumerate(blocks):
        start = m.start()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(agenda)
        block_text = agenda[start:end].strip()
        title = m.group(1).strip()

        print(f"\n--- Item {i + 1} of {len(blocks)} ---")
        print(block_text)

        while True:
            choice = input("\n[a]pprove / [m]odify / [r]eject / [s]kip: ").strip().lower()
            if choice in ("a", "m", "r", "s"):
                break
            print("Please enter a, m, r, or s.")

        action = {"a": "approve", "m": "modify", "r": "reject", "s": "skip"}[choice]
        note = ""
        if action == "modify":
            note = input("Your modification/ruling: ").strip()
        elif action == "reject":
            note = input("Why (for the record, optional): ").strip()

        rulings.append(MeetingRuling(item_title=title, action=action, ceo_note=note))

    return rulings


def cmd_meeting(hq: HQ, llm: LLM, config: BrainConfig) -> None:
    week = hq.current_week_key()
    agenda_path = hq.root / "meetings" / f"{week}-agenda.md"
    if not agenda_path.exists():
        print(f"No agenda for {week}. Run `brain ingest` first.")
        return

    agenda = agenda_path.read_text(encoding="utf-8")
    print(f"=== Board Meeting — {week} ===")

    rulings = _collect_rulings(agenda)
    if not rulings:
        print("Nothing to record; no minutes written.")
        return

    rulings_text = "\n".join(
        f"- {r.item_title}: {r.action.upper()}" + (f" — CEO note: {r.ceo_note}" if r.ceo_note else "")
        for r in rulings
    )
    user_message = (
        f"The {week} board meeting is over. Here is the agenda:\n\n{agenda}\n\n"
        f"---\n\nThe CEO's rulings:\n\n{rulings_text}\n\n"
        f"Today's date is {date.today().isoformat()}. Produce the meeting records."
    )

    system_blocks = build_system_blocks(config, hq, "meeting_synthesis.md")
    output = llm.call(system_blocks, user_message, max_tokens=config.max_tokens["meeting"])

    sections = _split_sections(output, MEETING_SECTION_RE)
    missing = [s for s in MEETING_OUTPUT_SECTIONS if s not in sections]
    if missing:
        # Don't lose the meeting: write the raw output as minutes and stop.
        hq.write_minutes(week, output)
        print(f"Warning: synthesis output missing sections {missing}. "
              f"Raw output saved as minutes; log/directives/escalations NOT auto-applied — review manually.")
        return

    minutes_path = hq.write_minutes(week, f"# Board Meeting Minutes — {week}\n\n{sections['Minutes']}\n")
    print(f"Minutes written: {minutes_path}")

    log_body = sections["Decision Log Entries"]
    entry_sections = _split_sections(log_body, LOG_ENTRY_HEADING_RE)
    for title, body in entry_sections.items():
        fields = dict(re.findall(r"^- ([A-Za-z ]+):\s*(.+)$", body, re.MULTILINE))
        departments_raw = fields.get("Affected departments", "")
        departments = [
            d.strip() for d in departments_raw.split(",")
            if d.strip() and d.strip().lower() != "none"
        ]
        hq.append_decision(
            DecisionEntry(
                date=date.today(),
                title=title,
                rationale=fields.get("Rationale", ""),
                decided_by=fields.get("Decided by", "CEO"),
                departments=departments,
            )
        )
    print(f"Decision log entries appended: {len(entry_sections)}")

    directive_body = sections["Directive Updates"]
    if directive_body.strip() != "None.":
        directive_sections = _split_sections(directive_body, LOG_ENTRY_HEADING_RE)
        for dept, content in directive_sections.items():
            dept_key = dept.strip()
            if dept_key not in hq.list_departments():
                print(f"  Warning: unknown department {dept_key!r} in directive updates — skipped.")
                continue
            # Directive content is required to be inside a fenced code block
            # so its internal ## headings can't collide with anything.
            fence_m = FENCED_BLOCK_RE.search(content)
            if not fence_m:
                print(f"  Warning: directive update for {dept_key} was not in a fenced block — skipped, review minutes manually.")
                continue
            hq.write_directive(dept_key, fence_m.group(1).strip() + "\n")
            print(f"Directive updated: {dept_key}")

    resolved_body = sections["Resolved Escalations"]
    resolved_count = 0
    for m in RESOLVED_LINE_RE.finditer(resolved_body):
        escalation_id, resolution = m.group(1), m.group(2).strip()
        try:
            hq.resolve_escalation(escalation_id, resolution=resolution, decided_by="CEO")
            resolved_count += 1
        except ValueError as e:
            print(f"  Warning: {e} — skipped.")
    print(f"Escalations resolved: {resolved_count}")


def cmd_directive(hq: HQ, llm: LLM, config: BrainConfig, department: str) -> None:
    if department not in hq.list_departments():
        print(f"Unknown department: {department!r}. Registered: {', '.join(hq.list_departments())}")
        return

    try:
        current = hq.read_directive(department)
    except FileNotFoundError:
        current = "(no directive on file yet)"

    print(f"=== Current directive: {department} ===\n")
    print(current)
    print("\nDescribe the changes you want (end with an empty line):")

    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and lines:
            break
        lines.append(line)
    changes = "\n".join(lines).strip()
    if not changes:
        print("No changes described; nothing to do.")
        return

    user_message = (
        f"Department: {department}\n\n"
        f"Current directive:\n\n{current}\n\n"
        f"CEO's requested changes:\n\n{changes}\n\n"
        f"Today's date is {date.today().isoformat()}."
    )
    system_blocks = build_system_blocks(config, hq, "directive.md")
    response = llm.call(system_blocks, user_message, max_tokens=config.max_tokens["directive"])

    print("\n" + response)

    if "[REQUIRES BOARD DECISION]" in response:
        print(
            "\nThis request includes a tier change, which is a board decision — "
            "the directive was NOT written. File it as an escalation or raise it "
            "at the next board meeting (`brain ingest` / `brain meeting`)."
        )
        return

    fence_m = FENCED_BLOCK_RE.search(response)
    if not fence_m:
        print("\nNo fenced directive block found in the response — nothing written.")
        return

    new_content = fence_m.group(1).strip() + "\n"
    confirm = input(f"\nWrite this directive to hq/directives/{department}.md? [y/N] ").strip().lower()
    if confirm == "y":
        path = hq.write_directive(department, new_content)
        print(f"Written: {path}")
    else:
        print("Not written.")


def cli() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="brain", description="Minivan Dads COO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show the company dashboard")

    ask_parser = subparsers.add_parser("ask", help="Ask the brain a question")
    ask_parser.add_argument("question", help="The question to ask")

    subparsers.add_parser("ingest", help="Synthesize reports into this week's agenda")
    subparsers.add_parser("meeting", help="Hold the board meeting on this week's agenda")

    directive_parser = subparsers.add_parser("directive", help="Create or revise a department directive")
    directive_parser.add_argument("department", help="Department name (e.g. market_intel)")

    args = parser.parse_args()

    config = load_config()
    hq = HQ(config)

    if args.command == "status":
        cmd_status(hq)
    elif args.command == "ask":
        llm = LLM(config)
        cmd_ask(hq, llm, config, args.question)
    elif args.command == "ingest":
        llm = LLM(config)
        cmd_ingest(hq, llm, config)
    elif args.command == "meeting":
        llm = LLM(config)
        cmd_meeting(hq, llm, config)
    elif args.command == "directive":
        llm = LLM(config)
        cmd_directive(hq, llm, config, args.department)


if __name__ == "__main__":
    cli()
