# Minivan Dads — The Brain (COO)

The operational brain of Minivan Dads Inc., a print-on-demand apparel brand
targeting minivan-driving dads. The brain is a Python CLI + local web console
that runs the COO loop: department agents research and file weekly reports
into **HQ** (a git-tracked Markdown filesystem — the company's single source
of truth), the brain synthesizes board-meeting agendas, walks the CEO through
rulings, moderates multi-agent boardroom debates, and writes every decision
back to HQ as a plain-text file change you can inspect in git.

Current state: Phase 1 (HQ + CLI) and its additions (executor framework,
boardroom, CEO dashboard) are complete; Phase 2 is live — the Market Intel
agent runs on a weekly schedule. Full specs live in `docs/specs/`; the phase
roadmap is at `hq/charter/roadmap.md`.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # installs the package editable + dev tools
cp .env.example .env                             # then paste your real ANTHROPIC_API_KEY
```

That registers `brain` as a console command inside the venv:

```bash
.venv/Scripts/brain.exe <command>      # or just `brain <command>` with the venv activated
```

(`python -m brain <command>` still works too.) The CLI finds the repo from
any directory inside it; set `BRAIN_ROOT` to run it from elsewhere.

## Commands

`brain --help` and `brain <command> --help` are the full cheat sheet — the
table below is the short version.

| Command | What it does | LLM call? |
|---|---|---|
| `brain status` | Company dashboard: reports filed, escalations (urgent first), last meeting, stale directives, actions last 7 days | No |
| `brain ask "<question>"` | Consult the brain ad hoc with full company context; offers to log any resulting decision | Yes |
| `brain ingest` | Reads reports since the last meeting → this week's agenda with `[BRAIN DECIDES]` / `[CEO REQUIRED]` tags and triaged escalations | Yes |
| `brain meeting` | Interactive board meeting: rule item by item, then minutes, decision-log entries, directive updates, and escalation resolutions land in HQ | Yes |
| `brain boardroom "<topic>"` | Multi-agent debate: blind positions → rebuttals → your floor (`@department` to question anyone) → synthesis → logged ruling with named dissents | Yes (many) |
| `brain directive <department>` | Create/revise a department's standing orders, validated against charter and tiers. Tier changes are refused — those are board decisions | Yes |
| `brain agent <department>` | Run a department agent's scheduled loop once by hand (research → report → escalations) | Yes (+ web search) |
| `brain rollback <action_id>` | Restore the pre-action snapshot for an executed action; auto-demotes that capability one rung | No |
| `brain dashboard` | Serve the CEO console at http://127.0.0.1:8712 | Only for chat |

At every decision prompt, the listed options are shortcuts — type anything
else and it becomes a conversation with the brain about the item on the
table. Voice input is your OS dictation key (Win+H) into any prompt.

## The CEO dashboard

```bash
brain dashboard        # then open http://127.0.0.1:8712
```

A local, read-mostly web console over HQ (localhost only, no auth). Four
tabs: **Dashboard** (stats, escalation inbox, recent decisions, this week's
agenda, ask-the-brain chat), **Departments** (card grid → directive, latest
report, actions taken, directive git history), **Boardroom** (run live
debates in the browser, past transcripts below), **Commands** (generated
from the CLI's own `--help`, so it never drifts). Everything visible
corresponds to a file in `hq/` — the dashboard holds no state of its own.

## Department agents (Phase 2+)

Agents are clones of one template (`brain/agent.py`): load directive → load
last report as memory → research via web search → write
`hq/reports/{dept}/{week}.md` → file escalations → exit. Blast radius of a
bad run: one bad report.

- **Market Intel** is live: GitHub Actions runs it Thursday nights
  (`.github/workflows/market-intel.yml`) and commits the report back. The
  `ANTHROPIC_API_KEY` repo secret powers it.
- Test a directive change without waiting a week: `brain agent market_intel`.
- Kill switch: set the department's `status` to `dormant` or `suspended` in
  `brain/config.yaml` — scheduled runs exit immediately.
- Future departments (Creative, Content, ...) activate by board decision:
  a real directive, a config status flip, and a cloned workflow file.

## The weekly rhythm

1. Thursday night: the Market Intel report lands automatically (check the
   repo's Actions tab if it doesn't).
2. Friday morning: `brain ingest` → read the agenda.
3. `brain meeting` → rule on each item (~20 minutes). Minutes, decisions,
   directive changes, and escalation resolutions all land in HQ.
4. `brain status` any morning for the 30-second glance.
5. Once a month: a deeper strategy review (`hq/meetings/monthly/`).

There are still no push notifications: an "urgent" escalation is surfaced
loudly the next time you run a command or open the dashboard, not before.

## Governance: why the brain can't overstep

Anything touching **money, brand identity, legal, or irreversible actions**
is always `[CEO REQUIRED]`. Enforced in code, not just prompted:

- Every LLM-proposed decision passes a post-processing check
  (`brain/governance.py`): self-checklist verification + an independent
  keyword backstop. Tags only ever upgrade toward `[CEO REQUIRED]`;
  malformed blocks fail safe.
- A directive rewrite that smuggles a tier/status change is never applied
  silently — the CEO must ratify it in so many words (CLI and dashboard).
- The action layer (`brain/executor.py`) is the only path to external
  writes: registered actions only, per-agent allowlists and bounds
  (`brain/actions/limits.yaml`, human-owned), capability ladder defaulting
  to dry-run (`hq/actions/capabilities.yaml`, machine-owned),
  snapshot-before-execute, append-only action log, `EXECUTOR_ENABLED=false`
  global kill switch. Every rejection is escalated, never dropped.
- The decision log (`hq/decisions/log.md`) is append-only — the brain never
  edits history.

## HQ layout

```
hq/
├── charter/        company.md (constitution), tiers.md (authority tiers), roadmap.md
├── directives/     standing orders per department
├── reports/        {department}/{YYYY}-W{WW}.md  (ISO week numbering)
├── decisions/      log.md — append-only decision log
├── escalations/    queue.md (open) / resolved.md (closed)
├── actions/        log.jsonl, snapshots/, capabilities.yaml (action layer)
└── meetings/       weekly agendas + minutes, boardroom transcripts, monthly/ reviews
```

## Tests

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

Covers the HQ layer, governance pass, executor validation matrix, boardroom
protocol, agent template, and dashboard endpoints. No API key needed —
tests never call the LLM.

## Session workflow (Claude Code)

This repo uses `project-context.md` + `project-memory.md` as cross-session
memory. Run `/start-of-day` at the start of every Claude Code session and
`/end-of-day` at the end (commits and pushes to GitHub).
