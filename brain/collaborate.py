"""Lightweight inter-department collaboration — the missing middle between a
one-department consult (@dept) and a full boardroom debate (#boardroom).

Two or more departments produce a JOINT work-product on a task: each
contributes in turn (seeing the task + prior contributions), then the brain
synthesizes one combined deliverable saved to hq/collaborations/. Unlike the
boardroom this is cooperative, not adversarial — no blind positions, no
rebuttals, no ruling — and unlike a meeting it writes no decisions and
changes no directives. It's a memo the departments made together, for CEO
review. (This is the exact capability directives already assume, e.g.
market_intel's "sanity-check finalist names with creative".)
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.boardroom import participant_blocks, slugify
from brain.config import BrainConfig
from brain.hq import HQ
from brain.llm import LLM


@dataclass
class Contribution:
    department: str
    text: str


class CollaborationSession:
    def __init__(self, llm: LLM, config: BrainConfig, hq: HQ,
                 task: str, departments: list[str]):
        self.llm = llm
        self.config = config
        self.hq = hq
        self.task = task
        self.departments = departments  # ordered — contribution sequence
        self.contributions: list[Contribution] = []
        self.deliverable = ""

    def _read_prompt(self, filename: str) -> str:
        return (self.config.prompts_root / filename).read_text(encoding="utf-8")

    def _rendered_contributions(self) -> str:
        if not self.contributions:
            return "(none yet — you are first)"
        return "\n\n".join(f"### {c.department}\n{c.text}" for c in self.contributions)

    def contribute_stream(self):
        """Each department contributes in turn, seeing the task and every
        prior contribution. Yields each Contribution as it lands."""
        for dept in self.departments:
            advisory = self.config.departments[dept].status != "active"
            blocks = participant_blocks(self.config, self.hq, "collaborate.md", dept, advisory)
            user_message = (
                f"MODE: contribute\n\n"
                f"Joint task: {self.task}\n\n"
                f"Contributions so far:\n\n{self._rendered_contributions()}\n\n"
                f"Add your department's part now."
            )
            text = self.llm.call(blocks, user_message,
                                 max_tokens=self.config.max_tokens["boardroom_floor"])
            contribution = Contribution(dept, text)
            self.contributions.append(contribution)
            yield contribution

    def _synthesis_blocks(self) -> list[dict]:
        return [
            {"type": "text", "text": "\n\n---\n\n".join([
                self._read_prompt("collaborate.md"),
                self.hq.read_company_charter(),
                self.hq.read_tiers(),
            ]), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Task: {self.task}\n\n"
                                     f"Contributions:\n\n{self._rendered_contributions()}"},
        ]

    def _synthesis_user(self) -> str:
        return f"MODE: synthesize\n\nProduce the combined deliverable for: {self.task}"

    def synthesize(self) -> str:
        self.deliverable = self.llm.call(
            self._synthesis_blocks(), self._synthesis_user(),
            max_tokens=self.config.max_tokens["boardroom_synthesis"],
        )
        return self.deliverable

    def synthesize_stream(self):
        """Token-delta generator for the dashboard; sets self.deliverable
        on completion, same as synthesize()."""
        chunks: list[str] = []
        for delta in self.llm.stream(
            self._synthesis_blocks(), self._synthesis_user(),
            max_tokens=self.config.max_tokens["boardroom_synthesis"],
        ):
            chunks.append(delta)
            yield delta
        self.deliverable = "".join(chunks)

    def save(self):
        week = self.hq.current_week_key()
        slug = slugify(self.task)
        content = (
            f"# Collaboration — {self.task}\n\n"
            f"Week: {week}\n"
            f"Departments: {', '.join(self.departments)}\n\n"
            f"---\n\n"
            + "\n\n".join(f"## {c.department}\n\n{c.text}" for c in self.contributions)
            + f"\n\n---\n\n## Combined deliverable\n\n{self.deliverable}\n"
        )
        return self.hq.write_collaboration(week, slug, content)

    def run(self) -> dict:
        """Blocking full run (CLI/tests): contributions -> synthesis -> save."""
        for _ in self.contribute_stream():
            pass
        self.synthesize()
        path = self.save()
        return {"path": path, "departments": self.departments,
                "deliverable": self.deliverable}
