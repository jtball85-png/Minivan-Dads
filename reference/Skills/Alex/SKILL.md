---
name: wrap-up
description: End-of-session wrap-up — update docs, prepare handoff, and commit all changes.
disable-model-invocation: true
---

# Session Wrap-Up

Perform the full end-of-session workflow in this exact order.
Do NOT skip steps. Do NOT push to remote unless explicitly asked.

---

## 1. Update `docs/SESSION_STATE.md`

Read the file first, then update these fields **in order**:

### a. LAST CONFIRMED STATE header
- **Date line**: Set to today's date. Increment the `(continuation #N)` counter by 1.
- **"Session ended with"**: One-line summary of the primary initiative(s) this session, using the `INITIATIVE_ID` — short description format.

### b. Recently Completed Initiatives
- Add a new bullet at the **top** of the list for each initiative completed this session.
- Format: `- **INITIATIVE_ID** (YYYY-MM-DD) — 1-2 sentence summary with key details (files changed, tests added, BL records).`
- Do NOT remove older entries — they scroll down naturally.

### c. ACTIVE / QUEUED / PARKED
- **Remove** any ACTIVE items that were completed this session.
- **Update** status text for ACTIVE items that progressed but aren't done.
- **Strike through** completed PARKED items with `~~` and add a `**COMPLETED**` note with the date and initiative ID.
- If new work was queued or parked, add it in the appropriate section.

### d. NEXT INTENDED ACTIONS
- Remove any items that were completed this session.
- Add any new next steps discovered during the session.
- Re-prioritize the list so the most urgent item is #1.

### e. OPERATOR-VERIFIED STATE (only if relevant)
- Update counts (students, modules, attendance rows, etc.) if data changed this session.
- Update infrastructure status if deployments or infra work happened.
- Update Known Issues: add new ones, mark resolved ones with ~~strikethrough~~.

---

## 2. Update `docs/reference/INDEX.md` (only if new BL records were created)

- Add one-line index entries in the correct section.
- Format: `- BL.DOMAIN.IDENTIFIER.NN (YYYY-MM-DD) — Brief label (≤15 words) → [domain_file.md](domain_file.md)`
- Do NOT write full record content in INDEX.md — it is an index only.

---

## 3. Update domain reference docs (only if new BL records were created)

- Write the full BL record (Status, Evidence, Implications, etc.) in the appropriate `docs/reference/<domain>.md` file.
- Every INDEX.md entry must have a corresponding full record in a domain file.

---

## 4. Write `docs/HANDOFF.md`

Write this file directly (do NOT use `scripts/session_handoff.py` — it produces a subset of what's needed). Follow this template exactly:

```markdown
# Session Handoff

**Generated**: YYYY-MM-DD HH:MM PST
**Branch**: `branch-name`
**Last commit**: `hash short message`
**Uncommitted changes**: summary of unstaged/untracked changes

---

## What Was Done This Session

- **INITIATIVE_ID** — Description of what was accomplished.
- Bullet per initiative or significant piece of work.

---

## Next Steps

### Priority heading (e.g., "Monday at School", "This Week")
1. Numbered, prioritized next actions.
2. Include context Claude needs to pick up the work.

### Lower priority heading
1. Items that can wait.

---

## Files Modified This Session

| File | Changes |
|------|---------|
| `path/to/file` | Brief description of changes |

---

## Recent Commits

- hash message (time ago)
- (from `git log --oneline -8`)

---

## Quick Links

- **Current state**: [docs/SESSION_STATE.md](SESSION_STATE.md)
- **BL record index**: [docs/reference/INDEX.md](reference/INDEX.md)
- **Domain references**: `docs/reference/*.md`
- **Execution plans**: `docs/plans/*.md`
- **Historical archive**: [docs/archive/SESSION_HISTORY_2025-2026.md](archive/SESSION_HISTORY_2025-2026.md)
- **Process docs**: `docs/process/`

---

END OF HANDOFF
```

Populate the template using:
- `git log --oneline -8` for recent commits
- `git status --porcelain` for uncommitted changes
- `git rev-parse --abbrev-ref HEAD` for branch
- `git log -1 --format="%h %s"` for last commit
- Your knowledge of what was done this session

Add any **session-specific quick links** (e.g., VPN plan, SMS plan) that the next session will need prominently.

---

## 5. Consistency check

Before committing, verify:
- [ ] Every new BL record in INDEX.md has a corresponding full record in a domain file.
- [ ] SESSION_STATE ACTIVE list matches reality (nothing completed still listed as active).
- [ ] SESSION_STATE NEXT INTENDED ACTIONS matches HANDOFF.md next steps (no contradictions).
- [ ] No stale dates or session numbers.

---

## 6. Commit

- Stage these files explicitly: `docs/HANDOFF.md`, `docs/SESSION_STATE.md`, `docs/reference/INDEX.md`, any modified domain reference files, and all code/config/template changes from the session.
- Do NOT stage: `data/` directory, `.env` files, `data/app.db`, `*.pyc`, `__pycache__/`.
- Write a concise commit message summarizing the session's work.
- Create the commit.
- Run `git status` after to confirm clean state.
