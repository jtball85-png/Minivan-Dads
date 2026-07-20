# Project: Minivan Dads — The Brain (COO)
Last updated: 2026-07-20 by Claude Code

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
Phase 1 complete and acceptance-tested: HQ + all five brain commands, plus the §7 additions from the 7/16 specs — free-text-everywhere CLI with `brain` console script, executor framework (registry/limits/capability ladder/rollback, fake connectors only), boardroom protocol (CLI + dashboard, honesty norm enforced structurally), and the CEO dashboard (four tabs, streaming ask chat, live boardroom). Phase 2 is live: market_intel is active at Tier 0 with a real directive, running Thursday nights via GitHub Actions (secret set, workflow active); its first live report and escalation are in HQ. Phase 3 (Creative + Content) is gated on the Phase 2 exit criteria — a directive change visibly changing the next report, plus a hard shop-open date — which need real calendar weeks and CEO work, not more code. Handoff docs live under `docs/specs/`; roadmap also at `hq/charter/roadmap.md`. 174 tests passing.

## Where we left off
Last commit: e6f2451 — First storefront agent run + directive tuning (Printful vs Etsy copy)
In progress: none
Branch: main

## What's next
- [ ] CEO-owned: open the Etsy shop (step zero — see `docs/design-to-store-pipeline.md`) and connect it to Printful, so the storefront agent's drafted listing copy + the ready-not-wired Etsy connector can go live
- [ ] Approve/adjust the escalated **$28** retail price on the quiet-game tee (until a price is set it cannot sell)
- [ ] CEO console review — build queue (from the fresh-eyes review): #4 consolidate UI surfaces gets a PLAN-MODE discussion first; then #7 mobile/remote access, #8 decision-log search, #9 first-run guide
- [ ] Phase 2 exit test: change market_intel's directive at a meeting and confirm the following Thursday's report reflects it
- [ ] Rule on open escalations at a meeting: ESC-002 (trademark prior-use), ESC-004 (handle/domain verification gap — now closed by the live-check tools), ESC-005 (ITU filing costs)
- [ ] CEO-owned: Class 25 trademark filing (PARKED pending alternatives + verification), name/domain/handle lockdown (minivandads.com registered to a 3rd party; .co/.shop available), hard shop-open date before Phase 3
- [ ] Update market_intel's directive to drop the now-stale "no live-check tooling" line (via #directive)

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
None blocking. Watch items: first scheduled market_intel run fires Thursday night — ESC-003 in the escalation queue is the reminder to verify it Friday before `brain ingest`; ESC-002 (trademark prior-use of "minivan dad"/"swagger wagon" phrasing) awaits a CEO ruling at the first real board meeting.

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
- 2026-07-20 — Built the first real connector (governed Printful product creation: account-level token auth, catalog reads, mockup generation, external_id-based rollback) and live-built the "quiet game" tee — serif front + "THE MINIVAN DADS" sleeve, 3 dark colorways, 15 variants, unpublished (f2b9b15, 428d7ee, eba95fd, e3fbba3); fixed a tiny-print bug via full-res files + explicit print positioning, verified against Printful's own placement previews (39abb50); added the repeatable design→store pipeline playbook (94f62bf); reframed to BOARD-run product management — unified ProductView + catalog snapshot, governed edit actions, storefront agent activated (Tier 1) proposing ### ACTION blocks through the executor, Etsy ready-not-wired, dashboard Products tab (c956c4b); first live storefront run escalated a $28 price rec + drafted listing copy, plus directive tuning for the Printful-vs-Etsy copy reality (e6f2451); 302 tests passing — Source: Claude Code
- 2026-07-19 — Cost visibility (#5) and top-commands-as-buttons (#6) built; Creative department activated as the second live agent (Tier 1, real directive + first report, ESC-008 raised); "Two rooms" garage/board model formalized in CLAUDE.md; garage-research and garage-design skills installed (design pipeline extended with real-template flat-preview compositing + a print-ready DPI export); real Printful product templates curated from a CEO-supplied folder; a full "quiet game" t-shirt design draft produced end-to-end and self-reviewed before presenting; brand-name research reopened — TheMinivanDads/MinivanDadClub/MinivanDadCrew domains re-verified available — Source: Claude Code
- 2026-07-17 — First real board cycle in the dashboard, then hardening + review fixes: brief-the-CEO (02109b4); CEO notification loop — sync banner, report-landed emails, #discuss, quick chips (ac13e81); SSE error guard (62eb6e2); stuck-boardroom fix + #abandon (cf9291c); live-check tools for agents — RDAP domains + honest handle checks (2d12436, fadd51f, 104b522); market_intel Phase-2 loop proven (reports auto-committed; minivandads.com found registered to a 3rd party); board record — brand-name research reopened, trademark PARKED (d2e1c64); fresh-eyes CEO review → built #collab (ed9029a), actionable Departments tab (a5d0cc0), 'needs you' panel (c22ac31); 188 → 238 tests — Source: Claude Code
- 2026-07-16 — Increment 6 polish (142ea6d); §7 additions A–D: free-text CLI + brain console script (0d670c0), executor framework (867bb1a), boardroom (e3a251b), read-only dashboard (d77b0e3); docs to docs/specs (42dddaf); dashboard chat + live boardroom (413eaed, 5367468); Phase 2 launch — market_intel live on GitHub Actions (0126b57, c4ce7e4); docs catch-up (e58fa00); chat env fix (7e7fbf4); one-click launcher + silent-failure defenses (12deb34, 600c466); dashboard command bar #commands/@dept (8b54fac); root cleanup (7354bfc); CLAUDE.md (80430ff); CEO's own boardroom session records committed — Source: Claude Code
- 2026-07-15 — Project initialized — Source: Claude Code
