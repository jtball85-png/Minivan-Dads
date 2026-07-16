# Minivan Dads — The Brain (COO)

The operational brain of Minivan Dads Inc., a print-on-demand apparel brand
targeting minivan-driving dads. The brain is a Python CLI that runs the
COO loop: it reads department reports out of **HQ** (a git-tracked Markdown
filesystem — the company's single source of truth), synthesizes board-meeting
agendas, walks the CEO through rulings, and writes every decision back to HQ
as a plain-text file change you can inspect in git.

Phase 1 = HQ + this CLI. Department agents (Market Intel, Creative, Content,
etc.) come in later phases — see `hq/charter/roadmap.md`.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env                             # then paste your real ANTHROPIC_API_KEY
```

Run everything from the repo root with the venv's Python:

```bash
.venv/Scripts/python.exe -m brain <command>
```

## Commands

| Command | What it does | LLM call? |
|---|---|---|
| `brain status` | Dashboard: who filed this week's report, open escalations (urgent first), last meeting date, stale directives (30+ days) | No |
| `brain ask "<question>"` | Ad-hoc consult. Loads charter + directives + recent decisions, answers, offers to log any resulting decision | Yes |
| `brain ingest` | Reads reports since the last meeting, writes `hq/meetings/{week}-agenda.md` with syntheses, proposed decisions tagged `[BRAIN DECIDES]` / `[CEO REQUIRED]`, and triaged escalations | Yes |
| `brain meeting` | Interactive board meeting. Walks each agenda item (`approve/modify/reject/skip`), then writes minutes, decision-log entries, directive updates, and resolves escalations | Yes |
| `brain directive <department>` | Create/revise a department's standing orders, validated against charter and tiers. Tier changes are refused — those are board decisions | Yes |

## The weekly rhythm

1. Reports land in `hq/reports/{department}/{YYYY}-W{WW}.md` (hand-filed in
   Phase 1; agents file them from Phase 2 on).
2. `brain ingest` → read the agenda it wrote.
3. `brain meeting` → rule on each item. Minutes, decisions, directive
   changes, and escalation resolutions all land in HQ automatically.
4. `brain status` any morning for the 30-second company glance.

There are no push notifications in Phase 1: an "urgent" escalation is
surfaced loudly the next time you run a command, not before.

## Governance: why the brain can't overstep

Anything touching **money, brand identity, legal, or irreversible actions**
is always `[CEO REQUIRED]`. This is enforced in code (`brain/governance.py`),
not just prompted: every LLM-proposed decision passes through a
post-processing check (self-checklist verification + an independent keyword
backstop) before it's written to HQ. Tags can only be upgraded to
`[CEO REQUIRED]`, never downgraded, and malformed blocks fail safe. The
decision log (`hq/decisions/log.md`) is append-only — the brain never edits
history.

## HQ layout

```
hq/
├── charter/        company.md (constitution), tiers.md (authority tiers), roadmap.md
├── directives/     standing orders per department
├── reports/        {department}/{YYYY}-W{WW}.md  (ISO week numbering)
├── decisions/      log.md — append-only decision log
├── escalations/    queue.md (open) / resolved.md (closed)
└── meetings/       weekly agendas + minutes; monthly/ for strategy reviews
```

## Tests

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

The suite covers the HQ layer (week discovery incl. year boundaries,
append-only log enforcement, atomic escalation moves) and the governance
pass. No API key needed — tests never call the LLM.

## Replaying the acceptance test

Drop a hand-written report at `hq/reports/market_intel/{current-week}.md`,
then run `brain ingest` followed by `brain meeting`. You should see a
sensible agenda with correctly separated tags, and after the meeting:
minutes, appended log entries, an updated directive, and any resolved
escalations — all as readable diffs in git. (The W29 files in HQ are the
original acceptance-test run, kept as a worked example.)

## Session workflow (Claude Code)

This repo uses `project-context.md` + `project-memory.md` as cross-session
memory. Run `/start-of-day` at the start of every Claude Code session and
`/end-of-day` at the end (commits and pushes to GitHub).
