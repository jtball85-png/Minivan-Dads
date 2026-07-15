# Project Memory
Last updated: 2026-07-15

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

### 2026-07-15 — Project kickoff
Ran /new-project. User supplied a full handoff brief (`minivan-dads-brain-project-brief.md`) and phase roadmap (`minivan-dads-phase-roadmap.md`) as the baseline instead of a fresh interview — instructed Claude to follow those docs and only confirm if scope slips or something's ambiguous, rather than re-asking settled questions. Filled project-context.md from the docs, confirmed gaps (local dir as clone location, brand new status, single env var) with the user directly. GitHub sync target for /end-of-day: https://github.com/jtball85-png/Minivan-Dads. Next: git init, set remote, commit, then begin Phase 1 build order from the brief (repo scaffold → hq.py → status/ask → ingest/meeting → directive).

<!-- end-of-day skill appends new sessions here -->
