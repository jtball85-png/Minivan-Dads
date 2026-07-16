# Project: Minivan Dads — The Brain (COO)
Last updated: 2026-07-15 by Claude Code

## What this project is
Minivan Dads Inc. is a print-on-demand apparel brand (Printful catalog, "Old Guys Rule" playbook) targeting minivan-driving dads, aiming for $200k+/yr net income or a seven-figure exit. This project is "The Brain" — Phase 1 of a multi-agent company system: a CLI orchestrator (COO) plus HQ, a git-diffable Markdown filesystem that is the company's single source of truth. Future department agents (Market Intel, Creative, Content, Product, Storefront, Customer, Paid Ads, Finance) will read directives from and write reports to HQ in later phases — not built yet, but the Phase 1 design must not box them out.

## Architecture decision
**Does this app need to save data between sessions or between users?**
- [x] Yes → Full stack (frontend + backend + database) — but unconventional: no web frontend/DB server. It's a CLI app whose "database" is a structured, git-tracked Markdown filesystem (HQ).

**Does this app need to hide secrets from the browser?**
- [x] N/A — no browser involved. `ANTHROPIC_API_KEY` is kept in a local `.env`, never committed.

**Current answer:** Full stack in spirit (persistent state + logic), implemented as CLI + filesystem, no server/database/frontend.

## Tech stack
| Layer | Tool/Language | Notes |
|---|---|---|
| Frontend | None | CLI only |
| Backend | Python | CLI app (`python -m brain <command>`), uses the `anthropic` Python SDK (Anthropic API) directly |
| Database | None (HQ) | HQ is plain Markdown + directories — human-readable, git-diffable, no DB |
| Auth | None | Single-operator (CEO) local tool |
| Deployment | Local only | No hosting in Phase 1 |
| AI / APIs | Anthropic API (`anthropic` SDK) | System prompts versioned as files in `brain/prompts/` |

## Data model
HQ is the data model — a structured file store, not a database:
- `hq/charter/` — company.md (constitution), tiers.md (authority tier definitions), roadmap.md
- `hq/directives/{department}.md` — standing orders per department
- `hq/reports/{department}/{YYYY}-W{WW}.md` — one report per department per week
- `hq/decisions/log.md` — append-only decision log (date, decision, rationale, decided-by, affected departments)
- `hq/escalations/queue.md` + `resolved.md` — open and closed items needing CEO judgment
- `hq/meetings/{YYYY}-W{WW}-agenda.md` / `-minutes.md` — weekly board meeting artifacts

Departments (registered in `config.yaml`, all dormant in Phase 1): market_intel, creative, content, product, storefront, customer, paid_ads, finance — each with `name`, `tier`, `status`, `report_cadence`.

## User flow
The CEO (human) runs CLI commands against HQ:
1. `brain status` — dashboard: which departments filed this week, open escalation count, last meeting date, stale directives (30+ days).
2. `brain ingest` — reads new reports since last meeting, writes `hq/meetings/{week}-agenda.md` with per-department synthesis, cross-department conflicts/opportunities, proposed decisions tagged [BRAIN DECIDES] or [CEO REQUIRED], and a triaged escalation queue.
3. `brain meeting` — interactive terminal session; brain walks CEO through the agenda, records rulings, writes minutes, appends to the decision log, updates directives, moves resolved escalations to `resolved.md`.
4. `brain ask "<question>"` — ad-hoc consultation, loads charter + directives + recent decisions as context, answers, logs any resulting decision.
5. `brain directive <department>` — generates/revises a department's standing directive interactively, validated against the charter and tiers.

## Current status
Brand new — no code written yet. This session is scaffolding the project's memory/tracking files and initializing git with the GitHub remote. Full build plan and acceptance criteria are defined in the handoff docs under `docs/specs/` (brief, roadmap, action-layer spec, boardroom/dashboard spec, progress summary, UX demos); the roadmap also lives at `hq/charter/roadmap.md`.

## Where we left off
Last commit: e056da5 — Implement brain directive command; Phase 1 CLI surface complete (increment 5)
In progress: none (only untracked .claude/ local config, intentionally not committed)
Branch: main

## What's next
- [ ] Increment 6: README usage section + governance keyword-list dogfooding pass — Claude Code

## File structure
```
/project-root
  /hq              → charter, directives, reports, decisions, escalations, meetings, actions (source of truth)
  /brain           → CLI (main.py), hq.py, governance, executor, boardroom, dashboard/, prompts/, config.yaml
  /docs            → reference guides
  /docs/specs      → handoff docs: brief, roadmap, action-layer + boardroom specs, progress summary, UX demos
  /reference       → reference material
  /tests           → pytest suite (no API calls)
  .env.example     → ANTHROPIC_API_KEY=
  pyproject.toml   → package + `brain` console script
  requirements.txt → -e . + dev tools
  README.md        → project readme
```

## Environment and credentials
- .env file: not yet created
- Variables needed: ANTHROPIC_API_KEY
- Where secrets are stored: local .env (not committed); `.env.example` documents the variable name only

## Key decisions made
- 2026-07-15 — Project initialized
- 2026-07-15 — Architecture: CLI + Markdown filesystem (HQ) as source of truth, no database/server/frontend
- 2026-07-15 — GitHub sync target set to https://github.com/jtball85-png/Minivan-Dads

## Known issues
None at this time — brand new build. Hardest anticipated part: getting the [BRAIN DECIDES] vs [CEO REQUIRED] triage logic right and keeping the decision log trustworthy and truly append-only.

## Context for each tool

### Chat
Thinking, planning, decisions, and fuzzy problems.
Flag architecture changes or scope changes before acting.

### Claude Code
Building and editing files. Tech stack: Python CLI (`anthropic` SDK / Anthropic API) reading/writing a Markdown filesystem (HQ) — no frontend, backend server, or database.
Run /start-of-day at the start of every session.
Run /end-of-day at the end of every session.

### Cowork
Browser tasks, desktop automation, file management.
Use project-context-updater.html on Cowork-heavy days.

## Change log
- 2026-07-15 — Scaffolded HQ + brain skeleton; implemented hq.py/governance.py with 44 passing tests; implemented all five CLI commands (status, ask, ingest, meeting, directive); brief's acceptance test passed end-to-end (commits 6ac7bc9, 57d882b, 3f86e86, 11f91c3, e056da5) — Source: Claude Code
- 2026-07-15 — Project initialized — Source: Claude Code
