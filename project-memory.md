# Project Memory
Last updated: 2026-07-21 (end of day)

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

## Session — 2026-07-21 (2)

**Focus:** CEO wanted to shift focus to Printful merch beyond apparel (posters, mugs, etc.), starting with an existing Illustrator design ("Bodysurf Fin") with multiple color combos already pushed to the Josh Ball Art store, and asked Claude Code to manage merch and the store going forward.

**Decisions made:**
- Store target confirmed as **Josh Ball Art** (not a Minivan Dads revival) for this POD merch line.
- CEO chose a recreation-as-test approach for the Bodysurf Fin design (no source file loaded — the real Illustrator/Photoshop files are on an external drive that wasn't connected this session); proper design/artwork handoff from that drive is explicitly pinned for a later session.
- CEO rejected the recreation outright as a poor visual match to the reference photo and instructed all draft files be deleted — done, nothing was ever pushed live.
- No work started on a Shopify connector; CEO said nothing to do on that right now.

**Problems solved:**
- None — the design recreation attempt did not reach an accepted state.

**Approaches discussed:**
- Confirmed via a live fetch of joshballart.com/collections/drinkware that "Bodysurf Fin" is already a real, live design across 3 drinkware products (mug, enamel cup, tumbler) with 7 real color combos on file: Red/Yellow, Peach/Burnt Orange, Blue/Pink, Peach/Blue, Lime Green/Electric Blue, Lavender/Teal, Black/White — useful reference for any future attempt.
- Clarified product/collection semantics: color variants of one design belong in a single Printful product listing (variants), not separate listings per color; "collection" is for grouping across different product types that share a design.
- Confirmed no Shopify MCP server or connector exists yet (`brain/connectors/` has Printful and Etsy only; `shopify.update_listing_copy`/`shopify.update_listing_images` are registered as allowed action *types* in `brain/actions/limits.yaml` but have no implementation). Building one requires the CEO to create a Shopify custom app/Admin API access token first (CEO-only, account-credential creation) — even once built, price/publish/brand-identity changes would still always escalate to the CEO per the governance model, never become autonomous.

**Left unresolved:**
- Real Bodysurf Fin recreation from the actual Illustrator/Photoshop source file — waiting on the CEO to connect the `E:\Products\Printful Products` external drive.
- Whether/when to build a real Shopify connector — no credentials created yet, no code started.

**Files changed this session:**
None committed. Design draft files (`garage/design/bodysurf-fin-2026-07-21*`) were created and then fully deleted per the CEO's rejection before anything was committed — net zero change to the repo.

## Session — 2026-07-21

**Focus:** Started on Minivan Dads roadmap items, but the CEO reconsidered POD apparel economics (thin margins) and pivoted the whole project to run their real art business, Josh Ball Art — then spent the rest of the session building the print-production pipeline: Lightroom/Photoshop workflow correction, a master-to-print-sizes derivation tool, and a printable cheat sheet with a real print-QA gate.

**Decisions made:**
- Company pivot ratified: the brain now runs **Josh Ball Art** (joshballart.com, Ventura CA — cyanotype/B&W photography/suminagashi/linocut, Jacquard-sponsored). Minivan Dads is PARKED, not deleted — charter archived to `hq/charter/archive/minivan-dads-company.md`, tee stays unpublished in Printful, decision logged 2026-07-21.
- Strategy ratified (CEO's own priority order): 1) originals, 2) giclée prints — mostly black & white photography plus cyanotype prints "priced like photos" — sizes 8×10/11×14/16×20 with white borders, 3) cyanotype/suminagashi workshops (popup + outdoor forage formats), 4) POD under a 30% margin floor (Sticker Mule to explore), 5) Jacquard supply shop maintained. Target: board runs 75–80% of day-to-day.
- Print partner: **FinerWorks chosen as primary** (CEO's call — biggest fine-art paper selection, praised archival matte; confirmed it has a free Shopify fulfillment app + API, so full automation is real, not aspirational). Prodigi = fallback, gicleetoday kept for hand-touched runs, theprintspace/creativehub ruled out (+20% fee, UK-centric).
- Master-file philosophy locked in: the master is exported **full native resolution, natural aspect ratio, borderless, never resized/resampled** — all sizing/bordering happens downstream, per-size, non-destructively, so one master serves every print size.
- Photoshop crop workflow settled: crop happens in Photoshop (not Lightroom) via the Crop tool with "Delete Cropped Pixels" unchecked (non-destructive); Lightroom stays for raw-level Develop (exposure/color/lens) only. The saved layered PSD is the permanent "negative"; the flattened export is a one-way "print" derived from it.
- Home test-printing must use `File > Print` (Photoshop-manages-colors, paper-specific ICC profile, printer driver color management OFF) — never `Image > Image Size`, which was the CEO's years-long habit and root cause of an under-resolution master.
- Lightroom catalog relocated in principle: catalog file must live on the **internal drive** (not the external SSD it shared with the photo library) — this is the diagnosed root cause of LRC's constant crashing, independent of the drive being SSD (the risk is USB connection reliability, not spinning-disk latency). Backups go to the external drive; correction (2026-07-21, caught when the CEO actually looked at the File menu): Lightroom Classic has no "Save Catalog As" command. The real move flow is: close Lightroom, copy the `.lrcat` file + its matching `...Previews.lrdata` folder from the external drive to the internal drive in File Explorer, then in Lightroom use File → Open Catalog… and point it at the new internal-drive copy (photo files themselves don't need to move).
- Deliverable format decision: for a print-oriented artifact, ship a **pre-verified PDF**, not just an HTML page relying on the hosted Artifact viewer's print path — the hosted URL's wrapper likely explains a 3-page/broken print the CEO saw even though the raw local file renders correctly (2 pages, verified).

**Problems solved:**
- CEO's first real master export (`Test.jpg`, 2385×1590) ran through the real derivation pipeline: 8×10 passed (265 DPI), 11×14 and 16×20 failed the 200 DPI floor (191/132 DPI) — confirmed the file was undersized, traced to the Image-Size-before-export habit, not a pipeline bug.
- Print-button dead click in the cheat sheet artifact: `window.print()` from a script is blocked by the Artifact's iframe sandbox (no visible error, just silently no-ops) — fixed by replacing the fake button with a `Ctrl+P` instruction badge (a real OS-level shortcut bypasses the sandbox restriction entirely).
- `verify_print.py`'s own first version failed silently (exit 0, no PDF) — root cause: Edge's headless PDF write finishes a beat after the process returns, and the script checked `pdf_path.exists()` immediately with no wait. Fixed with a poll loop (up to 10s) instead of a guessed fixed sleep. Also fixed absolute-vs-relative path handling for the GUI subprocess.

**Approaches discussed:**
- MCP servers for Photoshop exist (community/unofficial — `photoshop-mcp`, `adobe-mcp`, `dcc-mcp-photoshop` — via UXP plugin + local bridge), correcting an earlier flat "I can't be live in your Photoshop" — technically possible, but deliberately not adopted: the derive-from-a-clean-master architecture is safer (never touches the live PSD) and the only thing an MCP bridge would save is one Export click, not worth the broad unofficial-tool trust surface.
- Etsy's native Printful integration would auto-fulfill Etsy orders once connected — order/delivery tracking can mostly ride on the Printful connector already built, not a separate Etsy API build.

**Left unresolved:**
- Etsy shop for Josh Ball Art: confirmed absent from Google search entirely (likely dormant/empty) — CEO has not yet acted on connecting/reviving it.
- FinerWorks sample order not yet placed — waiting on the CEO to pick hero image(s) (one B&W photo + one cyanotype, since B&W tonal neutrality is the key test) and export a proper full-resolution master.
- Lightroom catalog has not yet actually been moved to the internal drive — diagnosed and planned, not executed.
- The hosted-Artifact-wrapper theory for the 3-page print discrepancy is a strong hypothesis, not confirmed (no way to authenticate and test the exact hosted URL from this environment) — worked around via a verified local PDF rather than root-caused on the platform side.
- API-key hygiene revisit still pending (carried over from 2026-07-20, see the standing `revisit-api-keys` memory).

**Files changed this session:**
```
 garage/prints/derive_prints.py                     | 104 ++++++++
 garage/prints/verify_print.py                      | 110 +++++++++
 garage/prints/workflow-cheat-sheet.html            | 268 +++++++++++++++++++++
 garage/prints/workflow-cheat-sheet.pdf             | (new, verified 2-page PDF)
 garage/prints/masters/, proofs/, ready/            | (pipeline test artifacts)
 garage/research/joshballart-phase0-print-partner-2026-07-21.md | 74 ++++++
 hq/charter/archive/minivan-dads-company.md         | 79 ++++++ (new, archived)
 hq/charter/company.md                              | 118 ++++----- (rewritten: Josh Ball Art)
 hq/decisions/log.md                                |   5 +
 hq/directives/creative.md                          |  55 ++---
 hq/directives/market_intel.md                      |  56 +++--
 hq/directives/storefront.md                        |  89 +++---- (x2 this session)
 16 files changed, 783 insertions(+), 175 deletions(-)  (5 commits: d228bef..846ad60)
```

## Session — 2026-07-20

**Focus:** Automating design→product — build the governed Printful connector (via plan mode) to turn approved designs into real products, then reframe into board-run product management across Printful/Etsy.

**Decisions made:**
- Built the first real connector `brain/connectors/printful.py` (account-level token auth via X-PF-Store-Id + store auto-resolve; catalog reads; governed `printful.create_product` through the executor; async mockup generation). Rollback uses a deterministic Printful `external_id` snapshotted pre-create, so a create is undone by `DELETE @external_id` without the executor needing the new product id.
- Live-built the real product: "Let's play the quiet game." tee — serif front + "THE MINIVAN DADS" left sleeve, 3 dark colorways (Black/Navy/Dark Grey Heather), S–2XL, 15 variants, unpublished, zero spend. Old test product cleaned up via governed rollback (rollback rehearsed live; capability auto-demoted supervised→dry_run as designed).
- Font/wordmark: CEO chose the SERIF (Georgia) look for the sayings over the researched bold-sans (Oswald/Bebas/Anton) — taste won over the research recommendation; sleeve wordmark = "THE MINIVAN DADS" (two words), not the run-together handle.
- File hosting: Printful fetches the design from a public URL at creation time; used litterbox/catbox (auto-expiring) since the repo is private — creation-time fetch only, so expiry is fine.
- Pipeline documented as a repeatable playbook (`docs/design-to-store-pipeline.md`): research→design→product→listing→publish→fulfill→learn, the 4 CEO-only walls (money/brand/legal/publish), and the API-access model (never browser login; access only via APIs the CEO authorizes).
- OWNERSHIP REFRAME (CEO correction): CEO does NOT want a console to operate products by hand — the BOARD (storefront agent) runs product upkeep and pulls the CEO in only at the walls or on request. Rebuilt the plan around this.
- Built board-run product management: unified `ProductView` model (`brain/products.py`, Printful now + Etsy-ready), catalog snapshot (`hq/products/catalog.json`+`.md`, read by dashboard/agents — "looking is free", no live API on view), governed edit actions (printful.update_product/set_retail_price, etsy.update_listing/set_price), storefront activated Tier 1 as a *doing* agent. `run_agent` now parses `### ACTION` blocks and routes them through the executor — copy edits preview (dry-run) until granted; price/brand always escalate. New `brain sync-products` command + read-only dashboard Products tab.
- Etsy built ready-but-NOT-wired (connector inert until a shop is connected); order/delivery tracking kept a SEPARATE follow-on (both CEO decisions in plan mode).
- Storefront's first live run: escalated a **$28** retail-price recommendation (~37% margin over ~$17.70 landed cost, within charter's $27–29 band); flagged "quiet game" as a saturated generic saying already sold verbatim elsewhere (NO trademark collision found) needing a hard minivan-dad differentiation angle; drafted a strong on-brand description + 7 SEO tags.

**Problems solved:**
- Tiny-print bug (CEO caught it): the real product printed the design ~4in, floating in the 12×16 area. Root cause: the serif front file was rendered at 1200×1600 @300dpi (=4×5.3in native) AND create sent no `position`. Fix: re-render at 3600×4800 (12×16in @300) AND send explicit fill positions per file. Lesson: verify against Printful's OWN stored placement preview, not the mockup generator (the generator independently scales to fill, which masked the bug).
- create_product only took one print file → extended to a `files` list so one product carries front + sleeve.
- Storefront's description/tags action was correctly REJECTED — a Printful product holds only a *name*; descriptions/tags live on the Etsy listing (not connected). Governance caught the shape mismatch; tuned the storefront directive so the agent parks copy as "Draft listing copy (ready for Etsy)" instead of proposing a doomed action (prompt-file fix, the standard fix).
- Invalid ANTHROPIC_API_KEY (401) blocked the first agent run — env issue: a second key made on the CEO's laptop disabled the original. CEO re-enabled the original; verified live with a 1-token call.

**Approaches discussed:**
- Etsy architecture: Printful's native Etsy integration auto-fulfills Etsy orders and pushes tracking, so order tracking can read Printful orders (no separate Etsy API needed just for fulfillment). CEO opens the shop + connects to Printful (browser OAuth on their side); the machine never logs into Etsy's website.
- Governance granularity: copy edits allowed (dry-run default, earn supervised/auto) vs. price ABSENT from allowed_actions → always rejected+escalated — mirrors the shopify copy/set_price pattern. Price/brand never earn autonomy.

**Left unresolved:**
- Etsy shop doesn't exist yet — CEO's step zero (open shop + connect to Printful) gates going live; the drafted description/SEO and the Etsy connector wait on it.
- $28 retail-price recommendation is escalated, awaiting CEO approval — until a price is set, the tee cannot sell.
- API-key hygiene needs a revisit (multiple Anthropic keys across the CEO's machines) — saved as a standing memory.
- Brand name (from prior sessions) still not finally decided.

**Files changed this session:**
```
 brain/actions/limits.yaml                   |  25 +-
 brain/actions/registry.py                   |  43 +++-
 brain/agent.py                              |  57 ++++-
 brain/config.yaml                           |   4 +-
 brain/connectors/etsy.py                    |  64 +++++
 brain/connectors/printful.py                | 263 +++++++++++++++++++++
 brain/dashboard/app.py                      |   7 +
 brain/dashboard/static/{app.js,index.html,style.css} | 43 +
 brain/hq.py                                 |  45 ++++
 brain/main.py                               | 114 ++++++++-
 brain/products.py                           | 147 ++++++++++++
 brain/prompts/agent_core.md                 |  21 ++
 docs/design-to-store-pipeline.md            | 125 ++++++++++
 garage/design/create_printful_product.py    | 112 +++++++++
 hq/directives/storefront.md                 |  66 +++++-
 hq/products/catalog.{json,md} + reports/storefront/2026-W30.md + actions/escalations trail
 tests/test_printful_connector.py            | 353 ++++++++++++++++++++++++++++
 tests/test_products.py                      | 111 +++++++++
 tests/test_storefront_agent.py              | 117 +++++++++
 tests/{test_hq_directives,test_limits}.py   |  11 +-
 33 files changed, 1947 insertions(+), 30 deletions(-)  (302 tests passing)
```

## Session — 2026-07-19

**Focus:** CEO console review build queue items #5 (cost visibility) and #6 (top commands as buttons), then Creative department activation, a garage/board operating model, and a full research-to-design pipeline, ending on reopening the brand-name decision.

**Decisions made:**
- Cost visibility (#5) built: per-call token/cost logging (`hq/actions/llm_usage.jsonl` via `hq.append_llm_usage`), `brain/pricing.py` rate table, `/api/costs` endpoint, `brain status` cost line, dashboard Cost card — cost tagged per command (ask/ingest/meeting/agent:dept/etc).
- Top commands as buttons (#6) built: plain-English "Quick actions" row on the Dashboard tab, not raw command syntax.
- Creative activated ahead of the Phase 2 exit gates on an explicit CEO decision (logged in `hq/decisions/log.md`, 2026-07-19): Tier 1, real directive written, first real weekly report produced (design-concept backlog, backup-handle brand-voice check citing market_intel's 2026-W29 Finding 6, ESC-008 raised).
- `brain/prompts/agent_core.md`'s "stay in tier" line was Tier-0-only phrasing — fixed to be tier-aware so Creative (Tier 1) gets correct ground rules.
- "Two rooms" operating model formalized in CLAUDE.md: Garage (CEO + Claude Code, ad hoc, ungoverned, not cost-tracked) vs. Dashboard/Board (charter/tier-governed departments, HQ-logged, cost-tracked). Rule: never call garage work "a loop" — collides with market_intel's GitHub Actions "loop".
- Installed `.claude/skills/garage-research/SKILL.md` (multi-agent independent research with a garage-to-board handoff step via `hq.write_research_exhibit()`) and built `.claude/skills/garage-design/SKILL.md` (research to SVG draft to flat composite preview to CEO-review checkpoint, hard stop before "push live").
- Real governed Printful connector (credentials, mockup generation, actual product creation) deliberately NOT built this session — stays a separate future decision; only garage-side drafting tooling was built.
- SVG rasterization on Windows: `cairosvg` doesn't work (no native Cairo/GTK3 runtime) — switched to `svglib` + `reportlab` + `pycairo` + `rlPyCairo`, added as a `garage` optional-dependency extra in `pyproject.toml` (not a core `brain` dependency).
- CEO supplied a real Printful product-template folder (`E:\Products\Printful Products`, ~773MB) — curated the t-shirt (Bella+Canvas 3001) and beanie subsets (~2.2MB) into `garage/design/printful-templates/`, excluding unrelated products and duplicates.
- Product-lineup research flagged stickers as a strong margin candidate and beanie-vs-structured-dad-hat as an open question with a seasonal ceiling on beanies — CEO deferred the beanie question to its own conversation; t-shirt/mug design work directed to draw from the sayings + color-combo research, not the beanie research.
- Brand-name reopening: TheMinivanDads.com, MinivanDadClub.com, and MinivanDadCrew.com all reconfirmed available (live RDAP checks); Etsy handle checks rate-limited (403, matches market_intel's own prior experience); Instagram/TikTok/X reconfirmed unverifiable via an independent method (WebFetch), consistent with the 2026-07-17 finding.
- CEO pasted a live Gmail password for `theminivandads@gmail.com` in chat — declined to attempt password-based login (no capability for it, and it reads as credential-stuffing to Google's own security systems); confirmed via the existing Gmail MCP connector that the currently-authorized account is a different, personal account; explained the OAuth-connector path forward is something the CEO has to do outside chat. No Instagram integration exists at all.

**Problems solved:**
- Dashboard still showed Creative as dormant after activation — root cause: `Minivan Dads HQ.bat`'s "already running? just open browser" check meant the stale server process (holding pre-activation config) never restarted; fixed by killing the stale process and starting a fresh one.
- A smoke-test run of `brain agent creative` accidentally overwrote the real first Creative report (same ISO week collision) — caught immediately, restored the original content verbatim, verified ESC-008 was untouched.
- First round of "10 road-trip one-liners" was invented marketing copy presented as if researched — CEO rejected it directly ("yours were aweful. was that really based on research?"); redone as real sourced research, with the CEO's own remembered lines banked as-is and separate confidence tiers for verified vs. unverifiable material.
- Printful's exact print-area dimensions require an API key (confirmed 401 without one) even though catalog browsing is free — `garage-design` built to prefer real local templates, then the API, then a labeled industry-standard approximation, in that order.
- First flat-preview render of the "quiet game" t-shirt design looked too-small-text at first glance — checked the actual 300 DPI print export before assuming a resolution problem; the real issue was vertical centering, not size or DPI; fixed and re-rendered before presenting, with the remaining imperfection (hand-picked coordinates, not real font-metric centering) stated plainly rather than left as a hidden defect.

**Approaches discussed:**
- Skills vs. app code for garage tooling: skills for ungoverned/no-credential/no-external-write work (research, design drafting); real `brain/` code + the existing executor/capability-ladder framework for anything touching real external writes, credentials, or money.
- "Garage narrows, board formalizes" as the standing pattern — messy/broad exploration happens in the garage first; only a narrowed, promoted exhibit goes to a department, and only when asked.
- Full research-to-preview pipeline (research, product selection, design, template-fit, flat preview, CEO approval, "ready to push live") built through CEO-reviewable flat preview; explicitly and permanently stopped short of the real Printful connector.

**Left unresolved:**
- Brand name: not finally decided. TheMinivanDads, MinivanDadClub, MinivanDadCrew all have confirmed-available .com domains; Etsy/Instagram/TikTok/X handle availability remains genuinely unverifiable with current tooling; Gmail/Instagram manual checks are on the CEO.
- Beanie vs. structured dad-hat product-lineup question — explicitly deferred to its own conversation.
- Sticker product addition — flagged as a strong candidate by research, not yet decided.
- Real Printful connector (credentials, mockup generation, actual product creation, "push live") — deliberately not built, remains a distinct future project.
- `theminivandads@gmail.com` Gmail connector — not yet authorized via Claude's own OAuth connector settings; that step is on the CEO.
- ESC-002, ESC-004, ESC-005, ESC-006, ESC-007, ESC-008 all still open; none ruled on at a board meeting this session.
- Phase 2 exit test (directive change visibly changing the next report) and the hard shop-open date — still open, untouched this session.
- T-shirt/mug design pass using the sayings + color-combo research — not completed; session moved to the brand-name conversation before it started.

**Files changed this session:**
23 files modified, 8 new untracked paths, none yet committed (nothing committed today until this end-of-day commit):
```
 .env.example                      |  4 +++
 CLAUDE.md                         | 26 ++++++++++++++++++
 brain/agent.py                    |  8 +++++-
 brain/config.yaml                 |  4 +--
 brain/dashboard/app.py            | 19 +++++++++++++
 brain/dashboard/chat.py           | 30 +++++++++++++++------
 brain/dashboard/static/app.js     | 57 +++++++++++++++++++++++++++++++++++++--
 brain/dashboard/static/index.html |  5 ++++
 brain/hq.py                       | 43 ++++++++++++++++++++++++++++-
 brain/llm.py                      | 34 ++++++++++++++++++++++-
 brain/main.py                     | 35 +++++++++++++++++++-----
 brain/models.py                   | 38 ++++++++++++++++++++++++++
 brain/prompts/agent_core.md       | 12 ++++++---
 hq/decisions/log.md               |  5 ++++
 hq/directives/creative.md         | 42 +++++++++++++++++++++--------
 hq/escalations/queue.md           |  6 +++++
 pyproject.toml                    | 10 +++++++
 tests/test_agent.py               | 24 +++++++++++++++++
 tests/test_chat.py                |  2 +-
 tests/test_collaborate.py         |  2 +-
 tests/test_commands.py            | 22 +++++++++++++--
 tests/test_hq_directives.py       | 12 +++++----
 tests/test_sync_and_discuss.py    |  4 +--
 23 files changed, 396 insertions(+), 48 deletions(-)
```
New untracked (not in the diff above): `.claude/skills/` (garage-research, garage-design), `brain/pricing.py`, `garage/` (research + design drafts, curated Printful templates, `compose_preview.py`), `hq/actions/` (llm_usage.jsonl, capabilities.yaml), `hq/reports/creative/2026-W29.md`, `tests/test_dashboard_costs.py`, `tests/test_hq_llm_usage.py`, `tests/test_hq_research_exhibits.py`, `tests/test_llm_usage_logging.py`, `tests/test_pricing.py`.

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
