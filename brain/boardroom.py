"""The boardroom: multi-agent deliberation on a topic.

Each participant is a SEPARATE model call with its own department context —
never the brain doing voices. The honesty norm is enforced structurally:
the positions round is blind (no participant sees another's position, and
the CEO has not yet been asked for anything, so their lean cannot leak).

Rounds: parallel-blind positions -> rebuttal (max 2, brain calls the
question) -> CEO floor (interactive, @department addressing) -> brain
synthesis naming the strongest objection -> CEO ruling, logged with named
dissents.

Position calls are sequential v1 — blindness is guaranteed by context
construction, not timing. If latency matters later, run them via
concurrent.futures.ThreadPoolExecutor over llm.call (the client is
thread-safe); no design change needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from brain.config import BrainConfig
from brain.hq import HQ
from brain.interaction import prompt_with_freetext
from brain.llm import LLM

CONVENE_RE = re.compile(r"^CONVENE:\s*(.+)$", re.MULTILINE)
DECLINE_RE = re.compile(r"^DECLINE:\s*(.+)$", re.MULTILINE)
SECOND_ROUND_RE = re.compile(r"^SECOND_ROUND:\s*(yes|no)\s*$", re.MULTILINE | re.IGNORECASE)
INTERJECT_RE = re.compile(r"^INTERJECT:\s*(\S+)\s*$", re.MULTILINE)
AT_DEPT_RE = re.compile(r"^@(\w+)\s+(.+)$", re.DOTALL)

MAX_REBUTTAL_ROUNDS = 2  # hard cap in code, whatever the moderator says


def slugify(topic: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "topic"


def participant_blocks(config: BrainConfig, hq: HQ, prompt_file: str,
                       dept: str, advisory: bool) -> list[dict]:
    """A department head's context: block 1 (cached) = instructions +
    charter + tiers; block 2 = that department's directive + last 2 reports,
    or the advisory flag when dormant. Shared by boardroom participants and
    standalone @department consults."""
    static = "\n\n---\n\n".join([
        (config.prompts_root / prompt_file).read_text(encoding="utf-8"),
        f"You are the head of the **{dept}** department.",
        hq.read_company_charter(),
        hq.read_tiers(),
    ])
    if advisory:
        dynamic = (
            "You are DORMANT: you have no directive and no reports yet. You are "
            "here in an advisory capacity — reason from the charter alone, and "
            "say so plainly when your lack of operating data limits your view."
        )
    else:
        parts = [f"### Your standing directive\n\n{hq.read_directive(dept)}"]
        for week in (hq.previous_week_key(), hq.current_week_key()):
            report = hq.read_report(dept, week)
            if report:
                parts.append(f"### Your report — {week}\n\n{report}")
        dynamic = "\n\n".join(parts)
    return [
        {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic},
    ]


@dataclass
class Participant:
    department: str
    advisory: bool  # dormant dept: charter-only context, flagged


@dataclass
class TranscriptEntry:
    round: str   # "positions" | "rebuttal-1" | "rebuttal-2" | "floor" | "synthesis" | "ruling"
    speaker: str  # department name | "brain" | "CEO"
    text: str


class BoardroomSession:
    def __init__(self, llm: LLM, config: BrainConfig, hq: HQ, topic: str,
                 input_fn=input, print_fn=print):
        self.llm = llm
        self.config = config
        self.hq = hq
        self.topic = topic
        self.input_fn = input_fn
        self.print_fn = print_fn
        self.participants: list[Participant] = []
        self.transcript: list[TranscriptEntry] = []
        self.synthesis_text = ""

    # -- context assembly ------------------------------------------------

    def _read_prompt(self, filename: str) -> str:
        return (self.config.prompts_root / filename).read_text(encoding="utf-8")

    def _participant_blocks(self, participant: Participant) -> list[dict]:
        return participant_blocks(
            self.config, self.hq, "boardroom_participant.md",
            participant.department, participant.advisory,
        )

    def _moderator_blocks(self) -> list[dict]:
        static = "\n\n---\n\n".join([
            self._read_prompt("boardroom_moderator.md"),
            self.hq.read_company_charter(),
            self.hq.read_tiers(),
        ])
        roster = "\n".join(
            f"- {name}: {d.status}" for name, d in self.config.departments.items()
        )
        return [
            {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Department roster:\n{roster}"},
        ]

    def _call_participant(self, participant: Participant, user_message: str,
                          tokens_key: str = "boardroom_position") -> str:
        return self.llm.call(
            self._participant_blocks(participant), user_message,
            max_tokens=self.config.max_tokens[tokens_key],
        )

    def _call_moderator(self, user_message: str) -> str:
        return self.llm.call(
            self._moderator_blocks(), user_message,
            max_tokens=self.config.max_tokens["boardroom_moderator"],
        )

    def _rendered_transcript(self) -> str:
        return "\n\n".join(
            f"[{e.round}] {e.speaker}:\n{e.text}" for e in self.transcript
        )

    def _say(self, round_name: str, speaker: str, text: str) -> None:
        self.transcript.append(TranscriptEntry(round_name, speaker, text))
        self.print_fn(f"\n[{speaker}]\n{text}")

    # -- rounds ------------------------------------------------------------

    def convene(self, override_depts: list[str] | None = None,
                all_departments: bool = False) -> bool:
        """Select participants. Explicit CEO override skips triage entirely;
        otherwise the moderator decides whether this topic deserves a debate
        at all (a 5-participant debate is ~12-20 model calls)."""
        if all_departments:
            selected = list(self.config.departments)
        elif override_depts:
            unknown = [d for d in override_depts if d not in self.config.departments]
            if unknown:
                self.print_fn(f"Unknown departments: {', '.join(unknown)}")
                return False
            selected = override_depts
        else:
            reply = self._call_moderator(
                f"MODE: triage\n\nTopic proposed for the boardroom:\n{self.topic}"
            )
            decline_m = DECLINE_RE.search(reply)
            if decline_m:
                self.print_fn(f"The brain declines to convene: {decline_m.group(1).strip()}")
                self.print_fn(f'Try: brain ask "{self.topic}"')
                return False
            convene_m = CONVENE_RE.search(reply)
            if convene_m:
                selected = [
                    d.strip() for d in convene_m.group(1).split(",")
                    if d.strip() in self.config.departments
                ]
            else:
                selected = []
            if not selected:
                # Malformed moderator output: the guard saves money, it must
                # never block the CEO — convene every active department.
                selected = [
                    name for name, d in self.config.departments.items()
                    if d.status == "active"
                ] or list(self.config.departments)[:4]

        self.participants = [
            Participant(
                department=name,
                advisory=self.config.departments[name].status != "active",
            )
            for name in selected
        ]
        roster = ", ".join(
            p.department + (" (advisory)" if p.advisory else "") for p in self.participants
        )
        self.print_fn(f"Convening: {roster}")
        return True

    def positions_stream(self):
        """Blind round, yielded per participant so the dashboard can render
        each position as it files: each user message contains only the topic
        and the instruction — no other positions, no CEO text (none exists
        yet)."""
        for p in self.participants:
            reply = self._call_participant(
                p,
                f"ROUND: positions\n\nTopic: {self.topic}\n\n"
                f"File your opening position (max 150 words) with your single "
                f"strongest reason. No other participant will see this until "
                f"everyone has filed.",
            )
            entry = TranscriptEntry("positions", p.department, reply)
            self.transcript.append(entry)
            yield entry

    def run_positions(self) -> None:
        self.print_fn("\n=== Opening positions (filed blind) ===")
        for entry in self.positions_stream():
            self.print_fn(f"\n[{entry.speaker}]\n{entry.text}")

    def rebuttals_stream(self):
        for round_no in range(1, MAX_REBUTTAL_ROUNDS + 1):
            transcript_so_far = self._rendered_transcript()
            for p in self.participants:
                reply = self._call_participant(
                    p,
                    f"ROUND: rebuttal\n\nTopic: {self.topic}\n\n"
                    f"The debate so far:\n\n{transcript_so_far}\n\n"
                    f"Rebut or update your position. Updating with a stated "
                    f"reason is encouraged; silent flips get flagged.",
                    tokens_key="boardroom_position",
                )
                entry = TranscriptEntry(f"rebuttal-{round_no}", p.department, reply)
                self.transcript.append(entry)
                yield entry

            if round_no == MAX_REBUTTAL_ROUNDS:
                break
            verdict = self._call_moderator(
                f"MODE: call_question\n\nTopic: {self.topic}\n\n"
                f"Debate so far:\n\n{self._rendered_transcript()}\n\n"
                f"Is a second rebuttal round warranted, or is the disagreement "
                f"fully drawn out? Reply SECOND_ROUND: yes or SECOND_ROUND: no."
            )
            m = SECOND_ROUND_RE.search(verdict)
            if not m or m.group(1).lower() == "no":
                break

    def run_rebuttals(self) -> None:
        current_round = ""
        for entry in self.rebuttals_stream():
            if entry.round != current_round:
                current_round = entry.round
                self.print_fn(f"\n=== Rebuttal round {current_round.split('-')[1]} ===")
            self.print_fn(f"\n[{entry.speaker}]\n{entry.text}")

    def floor_exchange(self, raw: str) -> list[TranscriptEntry]:
        """One CEO floor exchange: @dept routes to that participant (with a
        moderator-ruled interjection allowed), bare text goes to the brain.
        Appends to the transcript and returns the new entries — shared by the
        CLI loop and the dashboard endpoint."""
        start = len(self.transcript)
        self.transcript.append(TranscriptEntry("floor", "CEO", raw))

        at_m = AT_DEPT_RE.match(raw)
        if at_m and at_m.group(1) in {p.department for p in self.participants}:
            dept = at_m.group(1)
            participant = next(p for p in self.participants if p.department == dept)
            reply = self._call_participant(
                participant,
                f"ROUND: floor\n\nTopic: {self.topic}\n\n"
                f"Debate so far:\n\n{self._rendered_transcript()}\n\n"
                f"The CEO addresses you directly: {at_m.group(2)}",
                tokens_key="boardroom_floor",
            )
            self._say("floor", dept, reply)

            # Others may interject only if the brain rules it relevant —
            # at most one interjection per exchange.
            verdict = self._call_moderator(
                f"MODE: interjection\n\nTopic: {self.topic}\n\n"
                f"Debate so far:\n\n{self._rendered_transcript()}\n\n"
                f"Should any OTHER participant interject after that exchange? "
                f"Reply INTERJECT: <department> or NONE."
            )
            int_m = INTERJECT_RE.search(verdict)
            if int_m and int_m.group(1) in {p.department for p in self.participants} \
                    and int_m.group(1) != dept:
                interjector = next(
                    p for p in self.participants if p.department == int_m.group(1)
                )
                reply = self._call_participant(
                    interjector,
                    f"ROUND: floor\n\nTopic: {self.topic}\n\n"
                    f"Debate so far:\n\n{self._rendered_transcript()}\n\n"
                    f"The moderator has ruled your interjection relevant. "
                    f"Make it brief.",
                    tokens_key="boardroom_position",
                )
                self._say("floor", interjector.department, reply)
        else:
            reply = self.llm.call(
                self._moderator_blocks(),
                f"MODE: floor_discussion\n\nTopic: {self.topic}\n\n"
                f"Debate so far:\n\n{self._rendered_transcript()}\n\n"
                f"The CEO says: {raw}",
                max_tokens=self.config.max_tokens["boardroom_floor"],
            )
            self._say("floor", "brain", reply)

        return self.transcript[start:]

    def run_ceo_floor(self) -> None:
        """Interactive CLI loop. Free text is the PRIMARY channel here: @dept
        to address a department, bare text goes to the brain, 'done' ends."""
        self.print_fn(
            "\n=== CEO floor ===\n"
            "Address a department with @name (e.g. @creative what would change "
            "your mind?), talk to the brain with bare text, or 'done' to move "
            "to synthesis."
        )
        while True:
            raw = self.input_fn("\nfloor> ").strip()
            if not raw:
                continue
            if raw.lower() == "done":
                break
            self.floor_exchange(raw)

    def _synthesis_blocks(self) -> list[dict]:
        return [
            {"type": "text", "text": "\n\n---\n\n".join([
                self._read_prompt("boardroom_synthesis.md"),
                self.hq.read_company_charter(),
                self.hq.read_tiers(),
            ]), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Full debate transcript:\n\n{self._rendered_transcript()}"},
        ]

    def synthesis_stream(self):
        """Token-delta generator for the dashboard. On completion the full
        text is recorded on the session/transcript, same as run_synthesis."""
        chunks: list[str] = []
        for delta in self.llm.stream(
            self._synthesis_blocks(),
            f"MODE: recommendation\n\nTopic: {self.topic}\n\nProduce your synthesis.",
            max_tokens=self.config.max_tokens["boardroom_synthesis"],
        ):
            chunks.append(delta)
            yield delta
        self.synthesis_text = "".join(chunks)
        self.transcript.append(TranscriptEntry("synthesis", "brain", self.synthesis_text))

    def run_synthesis(self) -> str:
        self.synthesis_text = self.llm.call(
            self._synthesis_blocks(),
            f"MODE: recommendation\n\nTopic: {self.topic}\n\nProduce your synthesis.",
            max_tokens=self.config.max_tokens["boardroom_synthesis"],
        )
        self._say("synthesis", "brain", self.synthesis_text)
        return self.synthesis_text

    def collect_ruling(self, discusser_factory) -> str:
        choice = prompt_with_freetext(
            "\n[a]ccept recommendation / [m]odify / [r]eject — or keep talking: ",
            {"a": "accept", "m": "modify", "r": "reject"},
            discuss=discusser_factory(self.synthesis_text),
        )
        if choice == "accept":
            ruling = f"Adopted the brain's recommendation as synthesized: {self.synthesis_text}"
        else:
            detail = self.input_fn("Your ruling, in your words: ").strip()
            ruling = f"{choice.upper()}: {detail}" if detail else choice.upper()
        self.transcript.append(TranscriptEntry("ruling", "CEO", ruling))
        return ruling

    def _cli_ratify(self, dept: str, change: str) -> bool:
        """Default tier-ratification prompt for the interactive CLI."""
        self.print_fn(
            f"\nThe synthesized directive for {dept} includes a "
            f"tier/status change ({change}). Tier changes are explicit "
            f"board decisions — they are never applied silently."
        )
        return self.input_fn(f"Ratify this change for {dept} now? [y/N] ").strip().lower() == "y"

    def prepare_records(self, ruling_text: str) -> dict:
        """The records LLM call + parsing, NO writes. Returns everything
        commit_records needs, including the tier/status changes that require
        explicit CEO ratification. Split from commit so the dashboard can ask
        its ratification questions between the two without re-running the
        model (which would double-append decisions)."""
        from brain.records import (
            extract_directive_updates,
            parse_decision_entries,
            split_sections,
            tier_or_status_changed,
        )

        section_re = re.compile(
            r"^## (Decision Log Entries|Directive Updates|Ruling Summary)\s*$", re.MULTILINE
        )
        output = self.llm.call(
            self._synthesis_blocks(),
            f"MODE: records\n\nTopic: {self.topic}\n\n"
            f"The CEO's ruling:\n{ruling_text}\n\n"
            f"Today's date is {date.today().isoformat()}. Produce the records.",
            max_tokens=self.config.max_tokens["boardroom_synthesis"],
        )
        sections = split_sections(output, section_re)
        entries = parse_decision_entries(sections.get("Decision Log Entries", ""))
        updates, warnings = extract_directive_updates(
            sections.get("Directive Updates", "None."), self.hq.list_departments()
        )

        pending_ratifications = []
        for dept, content in updates.items():
            try:
                current = self.hq.read_directive(dept)
            except FileNotFoundError:
                current = ""
            change = tier_or_status_changed(current, content) if current else None
            if change:
                pending_ratifications.append({"dept": dept, "change": change})

        return {
            "ruling_text": ruling_text,
            "sections": sections,
            "entries": entries,
            "updates": updates,
            "warnings": warnings,
            "pending_ratifications": pending_ratifications,
        }

    def commit_records(self, prepared: dict, ratify_fn=None) -> dict:
        """All HQ writes for a prepared records bundle. `ratify_fn(dept,
        change) -> bool` decides whether a tier/status change smuggled into a
        directive rewrite gets applied; defaults to the CLI's inline [y/N]
        prompt."""
        ruling_text = prepared["ruling_text"]
        sections = prepared["sections"]
        entries = prepared["entries"]
        warnings = list(prepared["warnings"])
        pending = {p["dept"]: p["change"] for p in prepared["pending_ratifications"]}

        for entry in entries:
            self.hq.append_decision(entry)

        ratify = ratify_fn or self._cli_ratify
        written = []
        for dept, content in prepared["updates"].items():
            change = pending.get(dept)
            if change:
                # Tier/status moves are explicit board decisions, never a
                # silent side effect of a synthesized rewrite. The CEO is in
                # the room — make them ratify it in so many words.
                if not ratify(dept, change):
                    warnings.append(
                        f"directive update for {dept} included a tier/status "
                        f"change ({change}) the CEO did not ratify — skipped"
                    )
                    continue
                self.transcript.append(TranscriptEntry(
                    "ruling", "CEO",
                    f"Explicitly ratified for {dept}: {change}.",
                ))
            self.hq.write_directive(dept, content)
            written.append(dept)

        # Transcript is written last so any inline tier ratifications above
        # are part of the permanent record.
        week = self.hq.current_week_key()
        slug = slugify(self.topic)
        transcript_content = (
            f"# Boardroom — {self.topic}\n\n"
            f"Week: {week}\n\n"
            f"Participants: "
            + ", ".join(p.department + (" (advisory)" if p.advisory else "")
                        for p in self.participants)
            + "\n\n---\n\n"
            + self._rendered_transcript()
            + "\n\n---\n\n## Ruling Summary\n\n"
            + sections.get("Ruling Summary", ruling_text)
            + "\n"
        )
        transcript_path = self.hq.write_boardroom_transcript(week, slug, transcript_content)

        return {
            "transcript_path": transcript_path,
            "decisions": len(entries),
            "directives_updated": written,
            "warnings": warnings,
        }

    def finalize(self, ruling_text: str, ratify_fn=None) -> dict:
        """prepare + commit in one step — the CLI path."""
        return self.commit_records(self.prepare_records(ruling_text), ratify_fn)
