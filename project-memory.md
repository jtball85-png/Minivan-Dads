# Project Memory
Last updated: 2026-07-17 (end of day)

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

## Session — 2026-07-17

**Focus:** First real board cycle in the dashboard (Friday), then hardening/UX from live use, live-check tools for agents, and a fresh-eyes CEO console review with the top 3 fixes built.

**Decisions made:**
- Live-check tools for agents (brain/tools.py): read-only HTTP, so they bypass the executor and stay Tier 0 — checking if a URL exists writes/spends nothing. Domain checks via RDAP (free, no key, high confidence). Handle checks: only Etsy gives a real answer; Instagram/TikTok/X are "inconclusive/unverifiable" by design (proven, not guessed).
- Honesty over false confidence, twice: (1) agents must be reminded IN THE TRIGGER MESSAGE to use tools — passive system-prompt guidance was silently ignored (0 tool calls → 23 with the reminder); (2) Instagram/TikTok marker heuristic was proven worthless by a nonsense-handle test (returned "taken" for a string that can't exist) → now always "inconclusive", never a guess.
- CEO overruled the board (via boardroom): brand-name research REOPENED, "Minivan Dads" is a candidate not final, trademark filing PARKED pending live verification + a real slate of 5-10 alternatives. Reason: don't build brand equity on a name that might change.
- Notifications = GitHub issue on report-landing (github.token, no new secret) → GitHub emails the CEO if watching the repo. Real SMTP deferred.
- CEO review priority order adopted as the build queue (see What's next). Items 1-3 (collaboration, actionable departments, needs-you panel) built this session; 5 and 6 are next-session easy wins; 4 (consolidate UI) gets a plan-mode discussion first. All remaining next session.

**Problems solved:**
- Dashboard "hang forever" on Pull & build agenda = an Anthropic API 500 killing the SSE stream silently. Fixed with a _guard wrapper on all 8 streaming endpoints → any mid-stream exception becomes a visible {error} event; frontend surfaces "usually momentary, try again".
- Stuck-boardroom trap: server holds the debate, a page refresh loses the browser's memory of it → 409 with no way out. Fixed: /api/boardroom-status (renamed from /api/boardroom/status which collided with the {filename} transcript route), resume/abandon UI, and #abandon universal escape hatch.
- Brain wasn't briefing the CEO: #ingest showed a receipt not the agenda; #meeting jumped to rulings. Now #ingest renders the full agenda; #meeting opens with the briefing (syntheses + triage) behind a "Begin rulings" gate.
- Needs-you panel live-caught a real subtlety: an agenda built before newer escalations is STALE — holding a meeting on it misses them. Freshness now = agenda exists AND covers every open ESC id AND minutes newer than agenda → says "refresh the agenda" (#ingest) not "hold the meeting". (CEO used the button; W29 agenda now covers ESC-004/005.)
- Browser cache: old console page served after a restart (all the 404s traced to a stale server process too). Ctrl+F5 hard-refresh is the fix; noted for the CEO.

**Approaches discussed:**
- Fresh-eyes CEO console review (Opus persona). Headline: the tool is ahead of the business — a beautiful cockpit for a plane still in the hangar; set a hard "first product designed" date. Full priority list is now the What's next queue.
- Inter-department communication was hub-and-spoke with no spokes touching — #collab fills the missing middle (cooperative joint deliverable, no debate, no records). Boardroom = adversarial; collab = cooperative; consult (@dept) = one department.
- Art-business clone still on the horizon (advisory, prior session) — unchanged.

**Left unresolved:**
- CEO-owned, still open: Class 25 trademark filing (PARKED), name/domain/handle lockdown (minivandads.com is registered to a 3rd party; .co/.shop available), hard shop-open date before Phase 3, and market_intel's directive still has a stale "no live-check tooling" line the CEO can update via #directive.
- Open escalations awaiting a ruling: ESC-002, ESC-004, ESC-005 (W29 agenda now covers them — CEO can #meeting).
- CEO review items 4-9 not yet built (4 = plan-mode discussion next session; 5,6 = easy wins next; 7,8,9 later).
- "Tool ahead of business" — no product designed yet; standing strategic note.

**Files changed this session:**
Across ~14 commits (80430ff..c22ac31): new brain/tools.py, brain/collaborate.py, brain/prompts/{collaborate,consult}.md; brain/llm.py (client-tool loop + stream error handling reused), brain/agent.py (tool wiring + trigger reminder), brain/dashboard/{app.py,chat.py,static/app.js,static/index.html} (needs-you panel, sync banner, #collab/#discuss/#abandon, actionable departments, boardroom-status, error guard); brain/hq.py (write_collaboration, minutes collision-suffix); .github/workflows/market-intel.yml (issue notification); tests/ (test_tools, test_llm_tools, test_collaborate + additions) — 188 → 238 tests passing.

## Session — 2026-07-16

**Focus:** Increment 6 wrap-up, then the 7.15.26 Session handoff docs (progress summary §7): executor framework, boardroom, dashboard, chat surfaces; Phase 2 launch; terminal-free CEO workflow.

**Decisions made:**
- Capability-ladder modes live in machine-owned hq/actions/capabilities.yaml; limits.yaml stays 100% human-edited (auto-demotion never rewrites the human safety file).
- EXECUTOR_ENABLED unset = enabled — safe because every capability defaults to dry-run.
- Scheduler for Phase 2: GitHub Actions, Thursday nights 02:00 UTC Friday (9pm Central), committing reports back; ANTHROPIC_API_KEY set as repo secret via gh CLI (no key handoff — read from local .env).
- market_intel activated (dormant -> active, Tier 0) as a logged CEO decision; watch list consolidated into its directive.
- Tier/status changes smuggled into synthesized directive rewrites are never applied silently — CEO must ratify inline (meeting + boardroom paths); found via live dogfooding when a boardroom records call promoted creative to Tier 1 uninvited.
- The CEO does not want the terminal: Minivan Dads HQ.bat is the front door; the dashboard command bar (#commands, @department consults, plain text = ask) is the primary interface. Meeting runs as a guided flow in the browser.
- Cost framing for the CEO: "looking is free, thinking costs" — interface (terminal vs dashboard) changes nothing; model calls (ask/ingest/meeting/boardroom/agent) cost tokens either way.
- Spec docs + UX demos moved to docs/specs/; Project-Instructions.txt to docs/; .claude/commands committed (workflow is part of the repo); "7.15.26 Session" folder deleted after byte-identical verification.
- CLAUDE.md created (repo conventions, load-bearing rules, cost model).
- Repo verified PRIVATE on GitHub — strategy docs safe on the remote.

**Problems solved:**
- All the CEO's dashboard 404/405 errors traced to ONE root cause: a stale server process started before chat existed, running all day (static files served fresh, routes baked at startup — so the UI looked current but the API wasn't). Defense in depth added: /api/health endpoint, red "restart needed" banner (also when the server predates /api/health), chat failures print tracebacks and write dashboard_startup.log, launcher logs to dashboard.log.
- Launcher bat bugs: findstr without /c: ORs on the space (always matched, never started the server); LF-only line endings make cmd eat characters ('rem'->'m'); timeout dies without console stdin (replaced with ping sleep). Bat must be CRLF.
- Boardroom position truncation at max_tokens 600 (adaptive thinking shares the budget) — boardroom caps raised to 2500/1500/3000.
- Records model emitted literal "### {market_intel}" braces from the template placeholder — brace normalization in records.py + prompt fixes.
- load_dotenv now targets repo-root .env explicitly (console script runs from any cwd).
- Governance keyword backstop expanded (bare "logo", pricing, tier_change category, publish/account creation); regression test pins real W29 agenda prose as non-match.

**Approaches discussed:**
- Art-business clone (advisory, no build): the system is company-agnostic — clone = new private repo + new charter + tuned department roster (Curation, Production). Agents can't push pixels: print-prep is a deterministic script (master export -> per-product files), agents do judgment + Printful API via the executor (printful.create_product already registered). Clone AFTER the Minivan Dads loop is proven — trust transfers, code is an afternoon.
- Two-rooms operating model: dashboard = run the company (all operations), VS Code + Claude Code = evolve it (never moves to the dashboard). Friction from dashboard weeks becomes garage work orders. Prompt files are the agents' tunable skills; decision-log rationale trains taste; monthly review doubles as process retro; every bug becomes a regression test.

**Left unresolved:**
- Phase 2 exit test pending real time: Friday — check Actions tab (ESC-003), first real ingest+meeting, rule on ESC-002 (trademark prior-use); next week — directive change must visibly change the following Thursday report.
- CEO-owned: Class 25 trademark filing, name/domain/handle lockdown (market_intel dispatched diligence via the CEO's own boardroom session today), hard shop-open date before Phase 3.
- Deferred builds: meeting-in-dashboard exists via #meeting but CLI parity edge cases untested in anger; Phase 3 agents gated on Phase 2 exit; art-company clone on request.

**Files changed this session:**
73 files changed, 8144 insertions(+), 301 deletions(-) across 17 commits (142ea6d..80430ff + board records): brain/ gains actions/ (executor framework), boardroom.py, meeting.py, records.py, interaction.py, agent.py, dashboard/ (app, chat, static UI + command bar); .github/workflows/market-intel.yml; Minivan Dads HQ.bat; CLAUDE.md; docs reorganized into docs/specs/; tests 48 -> 188.

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
