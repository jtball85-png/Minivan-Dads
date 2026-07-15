# Project Memory
Last updated: 2026-07-15 (end of day)

This file captures decisions, reasoning, and session context that
project-context.md doesn't hold. It is Claude's memory between sessions.
Read automatically by /start-of-day. Updated automatically by /end-of-day.

---

## Key decisions (permanent record)

Decisions that shaped the project — keep these forever.

- 2026-07-15 — Architecture decision: CLI app + git-diffable Markdown filesystem (HQ) as the single source of truth, no database/server/frontend — reason: every state change must be human-readable and inspectable by the CEO in git; no infra needed for a single-operator tool.
- 2026-07-15 — Tech stack chosen: Python + Claude Agent SDK / Anthropic API — reason: specified in the handoff brief (`minivan-dads-brain-project-brief.md`).
- 2026-07-15 — GitHub sync target: https://github.com/jtball85-png/Minivan-Dads — used by /end-of-day for commits/pushes.
- 2026-07-15 — Phase 1 scope is strictly HQ + the brain CLI (status/ingest/meeting/ask/directive). No department agents, no Shopify/Printful/Meta integrations, no schedulers, no web UI — but design must not preclude them later (see `minivan-dads-phase-roadmap.md`).
- 2026-07-15 — Decision boundaries are hard rules enforced in code: money, brand identity, legal, and irreversible actions are always [CEO REQUIRED] — the brain may recommend but never rule on these.

---

## Sessions

Most recent session at the top.

## Session — 2026-07-15

**Focus:** Project kickoff (/new-project from the handoff brief), then the full Phase 1 build: HQ scaffold + all five brain CLI commands.

**Decisions made:**
- CLI framework: argparse (stdlib, no dependency) — brief calls for minimal surface.
- LLM integration: plain `anthropic` Python SDK with real API calls, NOT the claude-agent-sdk package. This corrects project-context.md's original "Claude Agent SDK" wording.
- Model: claude-sonnet-5 in config.yaml — cost-appropriate for structured synthesis per the charter's own "conservative spending" pillar; CEO can override.
- Charter addendum folded in from the CEO's chat session: two escalation channels (normal weekly vs. urgent-sorted-first), explicit "no push notifications in Phase 1 — urgent means loud at next command run" language, and a new monthly review artifact (hq/meetings/monthly/{YYYY}-{MM}-review.md).
- ISO week convention (date.isocalendar()) for all {YYYY}-W{WW} filenames — avoids calendar-year-boundary bugs.
- Governance enforced in code, not prompts: every LLM-proposed decision passes through governance.apply_governance() (checklist verification + independent keyword backstop) before being written to HQ; tags can only be upgraded to [CEO REQUIRED], never downgraded; malformed blocks fail safe to [CEO REQUIRED].
- Directive content in meeting-synthesis/directive LLM output must be inside a fenced code block — code extracts from the fence.
- HQ acceptance-test artifacts (fake market_intel W29 report, agenda, minutes, 3 decision-log entries, resolved ESC-001) committed as proof; can be purged before real Phase 2 use if desired.

**Problems solved:**
- Governance keyword backstop self-triggered on its own checklist line (the word "legal" in "legal=no") — fixed by scanning only title + recommendation text, not the whole block.
- Windows cp1252 console crashed on "≈" in LLM output mid-meeting — fixed by forcing UTF-8 on stdout/stderr in main.py.
- Meeting synthesis section splitter truncated directive rewrites at their first internal ## heading — fixed by splitting only on the four known section headings + requiring fenced directive content.
- ingest prompt originally told the model to ignore dormant departments entirely, which would have ignored the CEO's hand-filed acceptance-test report — changed to "dormant AND no report filed."
- No system Python on PATH (Microsoft Store stub) — real install at C:\Users\jball.VACE\AppData\Local\Python\bin\python3.exe (3.14.3); project uses .venv/Scripts/python.exe.

**Left unresolved:**
- Increment 6 (README usage section + governance keyword-list dogfooding pass) — next session.
- Nothing pushed to GitHub yet (https://github.com/jtball85-png/Minivan-Dads is set as origin; user hasn't said push).
- Minor model nit: `brain ask` once said "seven" departments instead of eight — prompt tuning candidate, not a code bug.

**Files changed this session:**
53 files changed, 2625 insertions(+) across 6 commits (8c35e0e → e056da5): full hq/ tree, brain/ package (main, hq, governance, llm, prompts, models, config + 5 prompt files), tests/ (44 passing), requirements.txt, pytest.ini, .env.example, .gitignore.

### 2026-07-15 — Project kickoff
Ran /new-project. User supplied a full handoff brief (`minivan-dads-brain-project-brief.md`) and phase roadmap (`minivan-dads-phase-roadmap.md`) as the baseline instead of a fresh interview — instructed Claude to follow those docs and only confirm if scope slips or something's ambiguous, rather than re-asking settled questions. Filled project-context.md from the docs, confirmed gaps (local dir as clone location, brand new status, single env var) with the user directly. GitHub sync target for /end-of-day: https://github.com/jtball85-png/Minivan-Dads. Next: git init, set remote, commit, then begin Phase 1 build order from the brief (repo scaffold → hq.py → status/ask → ingest/meeting → directive).

<!-- end-of-day skill appends new sessions here -->
