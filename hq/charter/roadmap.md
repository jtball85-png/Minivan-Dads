# Minivan Dads — Phase Roadmap

Companion to `minivan-dads-brain-project-brief.md`. The brief tells Claude Code WHAT to build in Phase 1; this document is the operating plan across phases — build work, CEO work, milestones, and exit criteria.

**Standing rules across all phases:**
- The weekly board meeting never skips, even with fake or thin data. The ritual is the product. Twenty minutes: `brain ingest` → agenda → rulings → minutes.
- Tier promotions are earned in the decision log, never assumed. Evidence of consistent good judgment → promotion proposal at a board meeting → logged decision.
- CEO-only actions in every phase: spending money, brand identity, legal, account creation, publishing.

---

## Phase 1 — The Brain + HQ (weeks 1–2)

**Build (Claude Code):** Repo scaffold, HQ file structure, seeded charter and tiers, `hq.py` layer with tests, then CLI commands in order: `status`, `ask`, `ingest`, `meeting`, `directive`.

**CEO work in parallel:**
- Stress-test `brain ask` with real strategic questions; check answers respect the charter.
- Lock the brand name; secure domain and social handles.
- Queue real decisions so the first board meeting has substance.

**Exit criteria:** The acceptance test from the brief passes — hand-written fake Market Intel report in, sensible agenda out with [BRAIN DECIDES] vs [CEO REQUIRED] correctly separated, meeting held, minutes + decision log + updated directive written to HQ, all readable in git.

---

## Phase 2 — Market Intel goes live (weeks 2–3)

**Build:** First real agent, Tier 0. A single scheduled script (cron / GitHub Actions timer): load its directive → load its last report (memory) → research via web search → write `hq/reports/market_intel/{week}.md` → append escalations if warranted → exit. Blast radius of any bug: one bad report.

**Watch targets (initial directive):** DadBod Apparel, Dad Gang, Etsy/Amazon dad-niche bestsellers, trending dad humor, seasonal moments, any minivan-adjacent design appearing anywhere.

**CEO work:** Hold the first REAL weekly board meeting. Rule on escalations. Change Market Intel's directive at a meeting and confirm the next report visibly reflects it.

**Exit criteria:** Trust in the loop — a directive change on Monday changes Thursday's report. The nervous system works end to end without manual prompting.

---

## Phase 3 — Creative + Content (weeks 3–5)

**Build:** Two Tier 1 agents cloned from the Market Intel template. New capability: they produce artifacts, not just reports.
- **Creative:** maintains a ranked design backlog in HQ — badge variants, sayings, concepts — each scored against brand voice. Weekly report = top 5 with rationale + what it killed and why.
- **Content:** builds the launch content bank — captions, meme formats, posting calendar — filed as ready-to-paste drafts.

**CEO work (highest leverage of the whole plan):** Taste. Approve/veto designs for Printful mockups. Every ruling is logged, so the brain learns your taste from the decision log. Also: finalize flagship badge, first Printful mockups, initiate the Class 25 trademark filing (the brain should be nagging via the escalation queue — by design).

**Exit criteria / milestones:** Flagship badge finalized. First products mocked up. Trademark filing initiated. 4+ weeks of launch content banked.

**Risk note:** This phase is the comfortable place to hide — polishing agents instead of launching shirts. Set a hard shop-open date before entering Phase 3.

---

## Phase 4 — Launch crew: Storefront + Customer (weeks 5–8, tied to shop opening)

Starts the week Shopify/Etsy goes live, not before.

**Build:** Two Tier 1 agents.
- **Storefront:** audits listings, drafts SEO fixes, monitors Printful fulfillment and friction points.
- **Customer:** drafts replies to every DM and review; builds email/SMS list strategy; reports customer language verbatim (product ideas live there).
- First connector integrations: READ access to store data, so reports say "your hat listing converted at 1.2%, here's the rewrite" instead of generic best practice.

**CEO work:** Open the shop. Publish content on cadence (drafts come from Content's bank). Click send/publish on everything the Tier 1 agents draft.

**Deliberately dormant:** Paid Ads and Finance stay off until there is real spend and revenue to manage. Turning on Finance with zero transactions generates noise, not signal.

**Exit criteria:** Shop live, first organic sales, review/DM turnaround under 24h using drafted replies, weekly reports grounded in real store data.

---

## Phase 5 — Money management + earned autonomy (post-revenue)

**Build:** Paid Ads (starts Tier 1 — proposes every spend) and Finance (Tier 0 — scorecard: P&L, unit economics, cash, ad ROAS, legal calendar). Write access to external systems only via explicit Tier 2 grants.

**Tier promotion examples (the reward system):**
- Content publishes 6 weeks of posts unedited → propose auto-scheduling promotion.
- Paid Ads proposes 10 straight budget moves the CEO would have made → earns a bounded sandbox (e.g., reallocate within approved $50/week).
- Storefront's listing fixes consistently approved untouched → earns typo-level direct edits.

**Never on the table for any agent:** money movement beyond explicit bounds, brand identity changes, legal commitments.
