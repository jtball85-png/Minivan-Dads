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
from brain.interaction import Exchange, prompt_with_freetext, render_exchanges
from brain.llm import LLM
from brain.models import DecisionEntry, MeetingRuling
from brain.prompts import build_system_blocks
from brain.records import (
    FENCED_BLOCK_RE,
    RESOLVED_LINE_RE,
    extract_directive_updates,
    parse_decision_entries,
    split_sections,
    tier_or_status_changed,
)


def make_discusser(llm: LLM, config: BrainConfig, hq: HQ, item_context: str):
    """Returns a discuss(ceo_text, history) callable for prompt_with_freetext.

    System blocks are built once (block 1 stays prompt-cached across turns);
    the running exchange history rides inside each user message, so llm.py's
    single-turn call shape is unchanged.
    """
    system_blocks = build_system_blocks(config, hq, "discussion.md")

    def discuss(ceo_text: str, history: list[Exchange]) -> str:
        prior = history[:-1]  # last entry is the message being sent now
        user_message = (
            f"Item currently on the table:\n\n{item_context}\n\n"
            + (f"Conversation so far:\n{render_exchanges(prior)}\n\n" if prior else "")
            + f"CEO: {ceo_text}"
        )
        return llm.call(system_blocks, user_message, max_tokens=config.max_tokens["discussion"])

    return discuss

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

    stats = hq.action_stats(days=7)
    print("\nActions (last 7 days):")
    if not stats:
        print("  none logged")
    else:
        for agent, counts in stats.items():
            parts = ", ".join(f"{result}: {n}" for result, n in sorted(counts.items()))
            print(f"  {agent:<15} {parts}")
        rejected = [
            r for r in hq.read_actions()
            if r.result == "rejected"
        ][-5:]
        if rejected:
            print("  Recent rejections:")
            for r in rejected:
                print(f"    {r.id} {r.action_type}: {'; '.join(r.reasons)}")


def cmd_ask(hq: HQ, llm: LLM, config: BrainConfig, question: str) -> None:
    system_blocks = build_system_blocks(config, hq, "ask.md")
    answer = llm.call(system_blocks, question, max_tokens=config.max_tokens["ask"])
    print(answer)

    m = DECISION_RECORD_RE.search(answer)
    if m:
        confirm = prompt_with_freetext(
            "\nLog this as a decision? [y]es / [n]o — or keep talking: ",
            {"y": "yes", "n": "no"},
            discuss=make_discusser(llm, config, hq, m.group(0)),
        )
        if confirm == "yes":
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


RULING_OPTIONS = {"a": "approve", "m": "modify", "r": "reject", "s": "skip"}


def _collect_rulings(agenda: str, discusser_factory) -> list[MeetingRuling]:
    """Walk the agenda's decision blocks interactively, one at a time.

    `discusser_factory(item_context) -> discuss callable` — free text typed at
    the ruling prompt becomes a sidebar conversation with the brain about the
    current item, recorded on the ruling.
    """
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

        discussion: list[Exchange] = []
        action = prompt_with_freetext(
            "\n[a]pprove / [m]odify / [r]eject / [s]kip — or just talk to the brain: ",
            RULING_OPTIONS,
            discuss=discusser_factory(block_text),
            transcript=discussion,
        )

        note = ""
        if action == "modify":
            note = input("Your modification/ruling: ").strip()
        elif action == "reject":
            note = input("Why (for the record, optional): ").strip()

        rulings.append(
            MeetingRuling(item_title=title, action=action, ceo_note=note, discussion=discussion)
        )

    return rulings


def _render_rulings(rulings: list[MeetingRuling]) -> str:
    """Render collected rulings (with any sidebar discussion) for synthesis."""
    parts = []
    for r in rulings:
        line = f"- {r.item_title}: {r.action.upper()}"
        if r.ceo_note:
            line += f" — CEO note: {r.ceo_note}"
        if r.discussion:
            line += "\n  Discussion during ruling:\n" + render_exchanges(r.discussion, indent="    ")
        parts.append(line)
    return "\n".join(parts)


def cmd_meeting(hq: HQ, llm: LLM, config: BrainConfig) -> None:
    week = hq.current_week_key()
    agenda_path = hq.root / "meetings" / f"{week}-agenda.md"
    if not agenda_path.exists():
        print(f"No agenda for {week}. Run `brain ingest` first.")
        return

    agenda = agenda_path.read_text(encoding="utf-8")
    print(f"=== Board Meeting — {week} ===")

    rulings = _collect_rulings(
        agenda, discusser_factory=lambda ctx: make_discusser(llm, config, hq, ctx)
    )
    if not rulings:
        print("Nothing to record; no minutes written.")
        return

    rulings_text = _render_rulings(rulings)
    user_message = (
        f"The {week} board meeting is over. Here is the agenda:\n\n{agenda}\n\n"
        f"---\n\nThe CEO's rulings:\n\n{rulings_text}\n\n"
        f"Today's date is {date.today().isoformat()}. Produce the meeting records."
    )

    system_blocks = build_system_blocks(config, hq, "meeting_synthesis.md")
    output = llm.call(system_blocks, user_message, max_tokens=config.max_tokens["meeting"])

    sections = split_sections(output, MEETING_SECTION_RE)
    missing = [s for s in MEETING_OUTPUT_SECTIONS if s not in sections]
    if missing:
        # Don't lose the meeting: write the raw output as minutes and stop.
        hq.write_minutes(week, output)
        print(f"Warning: synthesis output missing sections {missing}. "
              f"Raw output saved as minutes; log/directives/escalations NOT auto-applied — review manually.")
        return

    minutes_path = hq.write_minutes(week, f"# Board Meeting Minutes — {week}\n\n{sections['Minutes']}\n")
    print(f"Minutes written: {minutes_path}")

    entries = parse_decision_entries(sections["Decision Log Entries"])
    for entry in entries:
        hq.append_decision(entry)
    print(f"Decision log entries appended: {len(entries)}")

    updates, warnings = extract_directive_updates(sections["Directive Updates"], hq.list_departments())
    for warning in warnings:
        print(f"  Warning: {warning}.")
    for dept_key, content in updates.items():
        try:
            current = hq.read_directive(dept_key)
        except FileNotFoundError:
            current = ""
        change = tier_or_status_changed(current, content) if current else None
        if change:
            # Tier/status moves are explicit board decisions — never applied
            # as a silent side effect of synthesis. The CEO is here: ratify
            # in so many words, or it doesn't happen.
            print(f"\nThe synthesized directive for {dept_key} includes a tier/status "
                  f"change ({change}). Tier changes are explicit board decisions.")
            if input(f"Ratify this change for {dept_key} now? [y/N] ").strip().lower() != "y":
                print(f"  Skipped {dept_key} — raise it as its own agenda item when ready.")
                continue
        hq.write_directive(dept_key, content)
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
    confirm = prompt_with_freetext(
        f"\nWrite this directive to hq/directives/{department}.md? [y]es / [n]o — or keep talking: ",
        {"y": "yes", "n": "no"},
        discuss=make_discusser(
            llm, config, hq,
            f"Proposed new directive for {department}:\n\n{new_content}\n\n"
            f"CEO's original change request:\n\n{changes}",
        ),
    )
    if confirm == "yes":
        path = hq.write_directive(department, new_content)
        print(f"Written: {path}")
    else:
        print("Not written. (To refine it, run `brain directive` again with the adjusted ask.)")


def cmd_boardroom(hq: HQ, llm: LLM, config: BrainConfig, topic: str,
                  all_departments: bool = False, depts: str | None = None) -> None:
    from brain.boardroom import BoardroomSession

    session = BoardroomSession(llm, config, hq, topic)
    override = [d.strip() for d in depts.split(",")] if depts else None
    if not session.convene(override_depts=override, all_departments=all_departments):
        return

    session.run_positions()
    session.run_rebuttals()
    session.run_ceo_floor()
    session.run_synthesis()
    ruling = session.collect_ruling(
        discusser_factory=lambda ctx: make_discusser(llm, config, hq, ctx)
    )
    summary = session.finalize(ruling)

    print(f"\nTranscript written: {summary['transcript_path']}")
    print(f"Decision log entries appended: {summary['decisions']}")
    if summary["directives_updated"]:
        print(f"Directives updated: {', '.join(summary['directives_updated'])}")
    for warning in summary["warnings"]:
        print(f"  Warning: {warning}.")


def cmd_rollback(hq: HQ, config: BrainConfig, action_id: str) -> None:
    from brain.actions.limits import load_capabilities, load_limits
    from brain.actions.registry import REGISTRY
    from brain.executor import Executor

    executor = Executor(
        hq=hq,
        registry=REGISTRY,
        limits=load_limits(registry=REGISTRY),
        capabilities=load_capabilities(hq.root / "actions" / "capabilities.yaml"),
        connectors={},  # no live connectors until Phase 2+
    )
    try:
        record = executor.rollback(action_id)
    except ValueError as e:
        print(f"Cannot roll back: {e}")
        return
    print(f"Rolled back {record.id} ({record.action_type} by {record.agent}).")
    print("Capability demoted one rung; an escalation was filed for the next meeting.")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Pure and importable — the dashboard's Commands
    tab is generated from this parser so the reference can never drift."""
    fmt = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="brain",
        formatter_class=fmt,
        description=(
            "The Minivan Dads COO.\n\n"
            "The weekly rhythm:\n"
            "  1. Department reports land in hq/reports/{dept}/{week}.md\n"
            "  2. brain ingest    -> writes this week's board-meeting agenda\n"
            "  3. brain meeting   -> you rule; minutes/decisions/directives land in HQ\n"
            "  4. brain status    -> any morning, the 30-second company glance\n\n"
            "At every decision prompt, listed options are shortcuts only — type\n"
            "anything else and it becomes a conversation with the brain."
        ),
        epilog="Every state change the brain makes is a file write in hq/ you can read in git.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "status",
        help="Company dashboard (no API call)",
        formatter_class=fmt,
        description=(
            "The 30-second glance. Shows, without any model call:\n"
            "  - which departments filed this week's report (filed/missing/dormant)\n"
            "  - open escalations, urgent ones first and loud\n"
            "  - last board meeting date\n"
            "  - directives gone stale (not updated in 30+ days)\n\n"
            "Phase 1 has no push alerts: urgent items surface here, when you run this."
        ),
        epilog="Example: brain status",
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Consult the brain ad hoc (full company context)",
        formatter_class=fmt,
        description=(
            "Drop by the COO's office. Loads the charter, tier definitions, all\n"
            "directives, recent reports, the last 20 decisions, and the open\n"
            "escalation queue — then answers your question against them.\n\n"
            "If the answer amounts to a ruling, the brain drafts a Decision Record\n"
            "and asks before logging it to hq/decisions/log.md."
        ),
        epilog='Example: brain ask "should we expand the watch list to TikTok Shop?"',
    )
    ask_parser.add_argument("question", help="The question to ask")

    subparsers.add_parser(
        "ingest",
        help="Synthesize reports into this week's agenda",
        formatter_class=fmt,
        description=(
            "Reads every department report filed since the last board meeting and\n"
            "writes hq/meetings/{week}-agenda.md containing:\n"
            "  - a one-paragraph synthesis per department (honest about gaps)\n"
            "  - cross-department conflicts and opportunities\n"
            "  - proposed decisions tagged [BRAIN DECIDES] or [CEO REQUIRED]\n"
            "    (tags are verified in code — money/brand/legal/irreversible always\n"
            "    escalate to you, whatever the model wrote)\n"
            "  - the escalation queue triaged urgent / this-meeting / defer\n\n"
            "Run it Friday morning, or whenever reports are in."
        ),
        epilog="Example: brain ingest",
    )

    subparsers.add_parser(
        "meeting",
        help="Hold the board meeting on this week's agenda",
        formatter_class=fmt,
        description=(
            "The weekly 20-minute ritual. Walks you through the agenda item by\n"
            "item; rule with a/m/r/s or type anything to discuss the item with the\n"
            "brain first. When the meeting closes it writes:\n"
            "  - hq/meetings/{week}-minutes.md\n"
            "  - appended decision-log entries (with your reasoning)\n"
            "  - updated department directives\n"
            "  - resolved escalations moved to resolved.md\n\n"
            "Requires this week's agenda — run `brain ingest` first."
        ),
        epilog="Example: brain meeting",
    )

    directive_parser = subparsers.add_parser(
        "directive",
        help="Create or revise a department's standing orders",
        formatter_class=fmt,
        description=(
            "Shows the department's current directive, takes your changes in plain\n"
            "language, and drafts the full replacement — validated against the\n"
            "charter and the department's authority tier.\n\n"
            "Tier changes are refused here by design: promotions and demotions are\n"
            "board decisions, made at a meeting and logged."
        ),
        epilog="Example: brain directive market_intel",
    )
    directive_parser.add_argument("department", help="Department name (e.g. market_intel)")

    boardroom_parser = subparsers.add_parser(
        "boardroom",
        help="Convene a multi-agent debate on a topic",
        formatter_class=fmt,
        description=(
            "Opens a topic for genuine multi-department deliberation. Each\n"
            "participant is a separate model call with its own department context\n"
            "— never the brain doing voices — and your lean is withheld until\n"
            "opening positions are filed (charter honesty norm).\n\n"
            "Flow: blind positions -> rebuttals (max 2 rounds) -> your floor\n"
            "(@department to question anyone, bare text talks to the brain,\n"
            "'done' to move on) -> brain synthesis naming the strongest objection\n"
            "-> your ruling, logged with named dissents.\n\n"
            "Cost note: a 5-participant debate is ~12-20 model calls. The brain\n"
            "declines topics that `brain ask` can answer alone; --all or --depts\n"
            "overrides its judgment."
        ),
        epilog='Example: brain boardroom "September soft launch vs November full launch"',
    )
    boardroom_parser.add_argument("topic", help="The question to debate")
    boardroom_group = boardroom_parser.add_mutually_exclusive_group()
    boardroom_group.add_argument("--all", action="store_true", dest="all_departments",
                                 help="Convene every registered department")
    boardroom_group.add_argument("--depts", help="Comma-separated department list")

    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Restore the pre-action snapshot for an executed action",
        formatter_class=fmt,
        description=(
            "Restores the state captured before an executed action ran, via the\n"
            "same connector that ran it. The rollback is logged, and the agent's\n"
            "capability for that action type is automatically demoted one rung on\n"
            "the ladder (auto -> supervised -> dry-run) and raised at the next\n"
            "board meeting.\n\n"
            "Cannot restore: dry-run intents (nothing executed), actions marked\n"
            "irreversible in the registry (published posts, sent emails), or\n"
            "actions with no snapshot."
        ),
        epilog="Example: brain rollback ACT-2026-W31-0004",
    )
    rollback_parser.add_argument("action_id", help="The action id from hq/actions/log.jsonl")

    return parser


def cli() -> None:
    load_dotenv()

    parser = build_parser()
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
    elif args.command == "boardroom":
        llm = LLM(config)
        cmd_boardroom(hq, llm, config, args.topic,
                      all_departments=args.all_departments,
                      depts=args.depts)
    elif args.command == "rollback":
        cmd_rollback(hq, config, args.action_id)


if __name__ == "__main__":
    cli()
