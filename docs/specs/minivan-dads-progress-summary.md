# Progress Summary for Claude Code — Minivan Dads Inc.
**Covers: CEO/COO planning session, July 16, 2026 (from project-folder setup onward).**
**Purpose: bring Claude Code up to date on every decision and requirement agreed after the original project brief was written. Read alongside the docs in §6.**

---

## 1. Where the project stands

- The CEO has created the project folder in VS Code and started the Phase 1 build per `minivan-dads-brain-project-brief.md`.
- Architecture confirmed: CEO (human) → Brain/COO (orchestrator) → 8 department agents, all coordinating through the HQ Markdown filesystem. Nothing in the brief changed; everything below is ADDITIVE.

## 2. Decisions on interaction model & operating rhythm

These were settled in discussion and should be treated as product requirements:

**Dashboard timing.** Phases 1–4: the "dashboard" is VS Code + terminal (`brain status`, HQ folder in the sidebar, git history as audit trail). A real local web dashboard is deliberately deferred (~Phase 5) — EXCEPT that a read-only version may ship earlier because it's cheap (see boardroom/dashboard spec, Part B build order). Do not gold-plate UI pre-revenue.

**Three interaction modes:**
1. `brain meeting` — weekly structured session, brain drives, CEO rules.
2. `brain ask "<question>"` — ad-hoc consultation, full company context loaded, decisions logged.
3. Escalation queue — the async channel; agents raise hands into `hq/escalations/queue.md`; the brain triages; CEO never talks to agents directly (one conversation, eight agents).

**Board meeting cadence: weekly, non-negotiable, ~20 min.** Never monthly. Twice-weekly only during launch week/crisis. Reports land Thursday night; CEO runs `brain ingest` Friday morning (configurable).

**Operating rhythm at full operation (Phase 4+):**
- Daily (10–15 min): `brain status`, skim escalations, publish Content's drafts, approve Customer's drafted replies.
- Weekly (20 min + ~30 min follow-through): the board meeting; CEO's follow-through list = human-only actions (order samples, approve budgets in-platform, sign things).
- Monthly (~1 hr): strategy session — Finance trendlines, kill/scale review, tier promotions from decision-log evidence, roadmap phase check, brand-drift check against charter.
- Pre-launch (Phases 1–3) the curve is inverted: heavy build evenings, light meetings. Designed to flip at launch.

**Agent time cost:** direction happens once weekly via directive updates at the meeting; agent runs are minutes of scheduled compute; real cost is API tokens (tens of $/month at Phase 2–3 scale). Finance should eventually track model spend as a line item ("the COO's salary").

## 3. MAJOR SCOPE ADDITION — the Action Layer (agents as acting managers)

The CEO's directive: agents must ACT on direction, not just draft — website updates, shop management, marketing campaigns, data collection, reporting — and the CEO must be able to trust them like real managers, on evidence.

Full spec: `minivan-dads-action-layer-spec.md`. Headlines Claude Code must internalize:
- Single **executor** module; agents never call external APIs directly. Prompts express intent; the executor enforces law in code.
- Action **registry** (unregistered action = impossible action) + per-agent `limits.yaml` allowlists and bounds.
- **Capability ladder** per action type: dry-run → supervised live → autonomous-within-bounds; demotion on any rollback/override.
- Snapshots before every write + `brain rollback <action_id>`; immutable `hq/actions/log.jsonl`; per-agent and global kill switches.
- Hardcoded global denials (deletes, branding, payments, legal, cap increases) — always escalate, not configurable.
- Staging: Shopify development store for supervised-live phases. Money moves last in build order (Storefront hands before Paid Ads).
- Prompt-injection defense required: external content is data, never instructions; executor bounds are the real backstop.

## 4. MAJOR SCOPE ADDITION — Boardroom protocol + CEO Dashboard

The CEO's directive: board topics must be openable for genuine multi-agent DISCUSSION — each agent and the brain make their case, always arguing for what's best for the company; the CEO responds and debates with the team. Plus a CEO dashboard with command reference and per-department drill-downs.

Full spec: `minivan-dads-boardroom-dashboard-spec.md`. Headlines:
- `brain boardroom "<topic>"`: each participant is a SEPARATE model call with its own department context (charter + directive + last 2 reports) — never the brain doing voices.
- Debate rounds: parallel blind opening positions → rebuttal → CEO floor (interactive, address agents by name/@handle) → brain synthesis (must name the strongest objection and how it's handled) → CEO ruling logged with named dissents.
- **Honesty norm charter amendment** (add to `hq/charter/company.md`): argue for the company from your vantage; no turf defense; dissent on record required; consensus-seeking and deference to the CEO's presumed preference are charter violations. Enforced structurally: the CEO's lean is withheld from participants until opening positions are filed.
- Dashboard = local web app (`brain dashboard`), a VIEW over HQ files + chat surface, no state of its own. Four tabs: Dashboard / Departments / Boardroom / Commands (commands tab generated from CLI help so it never drifts).
- Boardroom acceptance test includes a conflict check: run a topic where Finance and Creative should disagree — if everyone agrees, the honesty norm is failing.

## 5. Interaction requirements added late (do not miss these)

- **Free text always available:** at EVERY decision point, in CLI and dashboard, suggested answers (numbered options / chips) are accelerators only. Typing anything else = discussion/question to the brain (or `@department` in boardroom). A persistent text input sits under any chips.
- **Voice v1 = OS dictation** into that text input (zero build). In-app speech-to-text is a possible later upgrade; do not build before the core loop works.
- **Console ergonomics:** register `brain` as a console script in `pyproject.toml` so the CEO types `brain status`, not `python -m brain status`. `brain --help` and per-command `--help` must be complete — they double as the CEO's cheat sheet. Interactive commands (`meeting`, `boardroom`) own the terminal for the session; plain typing inside the session, no prefix.

## 6. Document manifest (place in project root)

| File | Role |
|---|---|
| `minivan-dads-brain-project-brief.md` | Phase 1 build spec: HQ + brain CLI (original brief; §10 points to roadmap) |
| `minivan-dads-phase-roadmap.md` | Phases 1–5 detail; install at `hq/charter/roadmap.md` during scaffold |
| `minivan-dads-action-layer-spec.md` | Executor, limits, capability ladder, rollback, kill switches |
| `minivan-dads-boardroom-dashboard-spec.md` | Boardroom deliberation protocol + CEO dashboard (incl. free-text/voice reqs) |
| `board-meeting-demo.html` | UX reference: what `brain meeting` should feel like |
| `ceo-dashboard-demo.html` | UX reference: dashboard tabs + boardroom debate flow |

## 7. Consolidated build sequence (Phase 1 focus, additions slotted in)

1. Repo scaffold + HQ structure + seeded charter (INCLUDING the boardroom honesty norm from §4) + tiers + roadmap at `hq/charter/roadmap.md`.
2. `hq.py` read/write layer with tests.
3. CLI: `status` → `ask` → `ingest` → `meeting` → `directive`, with the free-text rule and console-script entry point from §5 baked in from the start.
4. Executor framework (action-layer spec §11 steps 1–2) — can run parallel to 3; no live connectors yet.
5. Boardroom protocol in CLI.
6. Read-only dashboard, then chat surfaces (boardroom spec Part B order).
7. Phase 2 (Market Intel agent + scheduler) only after the Phase 1 acceptance test in the brief passes.

## 8. Open items owned by the CEO (not Claude Code)

- Trademark filing (Class 25) — standing escalation until done.
- Name/domain/social handle lockdown.
- Hard shop-open date (guards against Phase 3 becoming a hiding place).
- API keys and scheduler ownership when Phase 2 arrives; Shopify dev store creation when the action layer goes live.
