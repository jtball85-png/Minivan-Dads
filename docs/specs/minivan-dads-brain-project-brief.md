# Project Brief: The Brain (COO) — Minivan Dads Inc.

**Handoff document for Claude Code. Read fully before writing any code.**

---

## 1. What we're building and why

Minivan Dads is a print-on-demand apparel brand (Printful catalog, Old Guys Rule playbook) targeting minivan-driving dads. Goal: $200k+/year net income or a seven-figure exit.

The company will be run by a multi-agent system:

- **CEO (human):** final sign-off on money, brand identity, legal, and anything irreversible.
- **COO ("the brain"):** the orchestrator being built in THIS project. Synthesizes all department reports, makes operational decisions, preps board meetings for the CEO, issues directives to department agents, triages escalations, and maintains the decision log.
- **Department agents (future phases):** independent scheduled agents (Market Intel, Creative, Content, Product, Storefront, Customer, Paid Ads, Finance). NOT built in Phase 1, but the infrastructure must anticipate them.

All coordination happens through a shared filesystem called **HQ**. Agents never talk to each other directly — they read directives from HQ and write reports/escalations back to HQ. The brain is the only component that reads everything.

## 2. Phase 1 scope (this build)

Build exactly two things:

1. **HQ** — the structured file store that is the company's single source of truth.
2. **The brain** — a CLI application (Python, using the Claude Agent SDK / Anthropic API) that runs the COO loop.

**Non-goals for Phase 1:** no department agents, no Shopify/Printful/Meta integrations, no schedulers/cron, no web UI. Do not build these yet, but do not paint us into a corner either.

## 3. Repository layout

```
minivan-dads/
├── hq/
│   ├── charter/
│   │   ├── company.md            # constitution — every agent inherits this
│   │   └── tiers.md              # authority tier definitions
│   ├── directives/
│   │   ├── _template.md
│   │   └── {department}.md       # standing orders per department
│   ├── reports/
│   │   └── {department}/
│   │       └── {YYYY}-W{WW}.md   # one report per department per week
│   ├── decisions/
│   │   └── log.md                # append-only decision log
│   ├── escalations/
│   │   ├── queue.md              # open items needing CEO judgment
│   │   └── resolved.md           # closed items with resolution + date
│   └── meetings/
│       └── {YYYY}-W{WW}-agenda.md and -minutes.md
├── brain/
│   ├── main.py                   # CLI entrypoint
│   ├── hq.py                     # all HQ read/write operations
│   ├── prompts/                  # brain system prompts, versioned as files
│   └── config.yaml               # model, paths, department registry
├── .env.example                  # ANTHROPIC_API_KEY=
├── requirements.txt
└── README.md
```

Design rule: **HQ is plain Markdown + directories.** Human-readable, git-diffable, no database. Every state change the brain makes must be a file write the CEO can inspect.

## 4. The brain's CLI commands

Implement these subcommands (e.g., `python -m brain <command>`):

### `brain status`
Print a dashboard: which departments have filed this week's report, open escalation count, last board meeting date, any stale directives (not updated in 30+ days).

### `brain ingest`
Read all new department reports since the last meeting. Produce `hq/meetings/{week}-agenda.md` containing:
- One-paragraph synthesis per department report
- Cross-department conflicts or opportunities the brain noticed
- The brain's proposed decisions, each tagged **[BRAIN DECIDES]** (within authority) or **[CEO REQUIRED]** (money, brand identity, legal, irreversible, or outside a tier boundary)
- Triaged escalation queue: urgent / this-meeting / defer

### `brain meeting`
Interactive session in the terminal. The brain walks the CEO through the agenda item by item, records rulings, then on completion writes:
- `hq/meetings/{week}-minutes.md`
- Appended entries to `hq/decisions/log.md` (format: date, decision, rationale, decided-by, affected departments)
- Updated `hq/directives/{department}.md` files reflecting new orders
- Moves resolved escalations from `queue.md` to `resolved.md`

### `brain ask "<question>"`
Ad-hoc consultation. Loads charter + latest directives + recent decisions as context, answers the CEO's question, and appends any resulting decision to the log. This is the "CEO drops by the COO's office" command.

### `brain directive <department>`
Generate or revise a department's standing directive interactively, validating it against the charter and tier definitions.

## 5. Brain behavior requirements

- **System prompt lives in `brain/prompts/`, not hardcoded.** It must load `hq/charter/company.md` and `hq/charter/tiers.md` into every session.
- **Decision boundaries are hard rules, enforced in code where possible:** anything involving spending money, changing brand identity (name, logo, core voice), legal commitments, or deleting/irreversible actions is ALWAYS tagged [CEO REQUIRED]. The brain may recommend, never rule, on these.
- **Every decision gets logged with rationale.** The log is append-only; the brain never edits history.
- **The brain reads before it thinks.** Every command that produces judgment must load: charter, tier defs, all current directives, reports from the current + previous week, the last 20 decision-log entries, and the open escalation queue.
- **Honest uncertainty.** When data is missing (e.g., a department hasn't reported), the brain says so in the agenda rather than guessing.

## 6. Charter v1 (seed `hq/charter/company.md` with this)

- **Mission:** Build Minivan Dads into a POD lifestyle brand reaching $200k+/yr net or a seven-figure exit, by owning the "minivan dad" identity the way Old Guys Rule owns aging surfers.
- **Brand voice:** ironic pride, "swagger wagon" energy. Screenshot-worthy humor. Never mean-spirited, never crude, never punching at moms/kids.
- **Strategy pillars:** (1) the badge is the business — "MINIVAN DADS" patch/badge, hat-first; (2) sayings collection is the viral engine feeding the badge; (3) bold creative, conservative spending — POD means we test loud ideas cheaply; (4) premium pricing ($27–29 tees), no perpetual-sale trap; (5) focus — one sharp joke, resist brand drift.
- **Hard guardrails:** no spend without CEO approval; no legal commitments without CEO; trademark filing (Class 25, "Minivan Dads" word mark) tracked as a standing priority; failure to protect the brand is the only unacceptable outcome.

## 7. Authority tiers (seed `hq/charter/tiers.md`)

- **Tier 0 — Read-only:** research and report. Touches nothing external.
- **Tier 1 — Draft-only:** produces ready-to-ship artifacts (designs, posts, replies, listings). A human publishes.
- **Tier 2 — Act-within-bounds:** executes inside explicit pre-approved limits written in its directive (e.g., "reallocate ad spend within approved $50/week"). Every action logged.
- **Tier 3 — Full autonomy:** reserved; requires explicit CEO grant per capability. Never for money movement, brand identity, or legal.

Every directive file must declare the department's current tier. Tier changes are decisions: they happen at board meetings and get logged.

## 8. Department registry (config.yaml)

Register all eight departments now (market_intel, creative, content, product, storefront, customer, paid_ads, finance) with fields: `name`, `tier`, `status` (active/dormant), `report_cadence`. All start `dormant` except none — Phase 1 has no active agents. The brain's `status` and `ingest` commands should gracefully handle dormant departments and empty report folders.

## 9. Build order & acceptance criteria

1. Scaffold repo + HQ structure with seeded charter, tiers, templates.
2. `hq.py` read/write layer with tests (report discovery by week, append-only log writes, escalation moves).
3. `brain status` and `brain ask`.
4. `brain ingest` and `brain meeting`.
5. `brain directive`.

**Phase 1 is done when:** the CEO can drop a hand-written fake report into `hq/reports/market_intel/`, run `brain ingest`, get a sensible agenda that separates [BRAIN DECIDES] from [CEO REQUIRED], run `brain meeting`, make rulings, and see correct minutes, decision-log entries, and an updated directive appear in HQ — all human-readable in git.

## 10. Phase roadmap (context, do not build)

- **Phase 2:** Market Intel agent (Tier 0) on a scheduler — proves the directive→report loop with zero risk.
- **Phase 3:** Creative + Content agents (Tier 1) — designs and content bank for launch.
- **Phase 4:** Storefront + Customer agents at shop launch; Paid Ads + Finance once there's spend and revenue.
- **Phase 5:** Tier promotions and connector integrations (Shopify, Printful, Meta) as trust is earned.

Departments are clones of a shared agent template that reads its directive from HQ and writes reports back — keep `hq.py` clean enough to be imported by them later.

Full phase detail (deliverables, CEO workstreams, exit criteria, tier-promotion rules) lives in `minivan-dads-phase-roadmap.md` — place it at `hq/charter/roadmap.md` when scaffolding HQ.
