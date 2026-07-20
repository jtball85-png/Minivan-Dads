# CLAUDE.md — Minivan Dads: The Brain

Minivan Dads Inc. is a POD apparel company run by a multi-agent system. This
repo is both the company (the `hq/` files) and the machine that runs it (the
`brain/` package). The human is the CEO — a non-programmer. Explain in plain
language, describe outcomes over implementations, and never require the
terminal for company operations (the dashboard is the CEO's surface;
`Minivan Dads HQ.bat` is the front door).

## Two rooms: Garage vs. Dashboard

Two distinct places work happens, and the CEO will often say which one they
mean without naming it explicitly — infer from what's being asked:

| | **Garage** | **Dashboard / Board** |
|---|---|---|
| Who | CEO + Claude Code | market_intel, creative, ... |
| Governed by | Nothing formal | Charter, tiers, directives |
| Output | Wherever we decide (chat, `garage/`) | `hq/reports/`, `hq/decisions/`, cost-logged |
| Trigger | Slash commands, skills, direct ask | `#agent`, `#meeting`, `#boardroom` |

**Default to the garage.** Escalate to the board only when the work needs
to (a) persist as a department's ongoing memory, (b) carry the charter's
brand-voice judgment *logged as the board's own*, or (c) become a decision
that belongs in `hq/decisions/log.md`. A one-off "what's out there" look
almost never needs the board — it's cheaper and faster in the garage, and
nothing is lost since there's no continuity value to throw away on a first
pass. See `.claude/skills/garage-research/SKILL.md` for the research
workflow, including how a garage finding gets promoted to a board exhibit.

**Never call garage work "a loop."** That word is already taken —
market_intel's Thursday GitHub Actions run is "the loop" in this project's
own history. A repeating garage task is a *garage loop*, said explicitly,
never bare "a loop."

## Commands

```bash
.venv/Scripts/python.exe -m pytest tests/ -q     # run tests (no API key needed)
.venv/Scripts/brain.exe <command>                # the CLI (status/ask/ingest/meeting/boardroom/directive/agent/rollback/dashboard)
.venv/Scripts/pip install -e ".[dev]"            # reinstall after pyproject changes
```

Python 3.14 venv at `.venv/`. No system `python` on PATH — always use the
venv paths above. The `brain` console script finds the repo root from any
cwd (BRAIN_ROOT env var or upward walk for `hq/charter/company.md`).

## Load-bearing architecture rules

- **HQ is plain Markdown + directories, no database.** Every state change
  the brain makes must be a file write the CEO can read in git.
- **`brain/hq.py` is the ONLY code that touches files under `hq/`.**
  Everything else goes through an `HQ` instance.
- **`hq/decisions/log.md` and `hq/actions/log.jsonl` are append-only.**
  Only `append_decision`/`append_action` write them, `'a'` mode only —
  never rewrite history.
- **Governance is code, not prompts** (`brain/governance.py`): money, brand,
  legal, irreversible ⇒ always [CEO REQUIRED]; tags only upgrade toward the
  CEO. Tier/status changes in synthesized directives require explicit CEO
  ratification (`records.py::tier_or_status_changed` guard in both meeting
  and boardroom paths).
- **`brain/executor.py` is the only path to external writes.** Registered
  actions only; limits.yaml is human-owned, hq/actions/capabilities.yaml is
  machine-owned; missing capability = dry-run; rejections escalate, never
  drop. No live connectors yet (Phase 2 has none).
- **`brain/dashboard/app.py` never imports `brain.llm`** (AST-enforced by a
  test). Chat/LLM routes live in `brain/dashboard/chat.py` only.
- **Agent prompts are files in `brain/prompts/`, never hardcoded strings.**
  Tuning a prompt file is the standard fix for disappointing agent output.
- **ISO week keys everywhere** (`date.isocalendar()`, `{YYYY}-W{WW}`,
  zero-padded).
- LLM calls use a two-block system prompt: block 1 (instructions + charter +
  tiers) carries `cache_control`; block 2 is the dynamic weekly context.
  See `brain/prompts.py::build_system_blocks`.

## Conventions

- Every bug found becomes a regression test (`tests/`, FakeLLM/FakeConnector
  doubles — tests never call the API).
- Session objects (BoardroomSession, MeetingSession) split LLM-call
  preparation from HQ writes (`prepare_* / commit_*`) so dashboard
  ratification round-trips never double-append records.
- Commit style: imperative summary line, body explains what and why, ends
  with the Co-Authored-By Claude trailer. Push after committing (the CEO's
  sync convention).
- Cross-session memory: `project-context.md` + `project-memory.md`,
  maintained by `/start-of-day` and `/end-of-day` — run them at session
  start/end.
- Specs and handoff docs live in `docs/specs/`; the phase roadmap (what to
  build when, and what's deliberately deferred) is also at
  `hq/charter/roadmap.md`. Respect phase gates — don't build ahead of them.

## Cost model (explain to the CEO when relevant)

Looking is free, thinking costs: `status`, the dashboard views, and file
reads make no API calls; `ask`/`ingest`/`meeting`/`boardroom`/`agent` call
the model (key in `.env` locally, GitHub secret for the Thursday scheduled
agent run).
