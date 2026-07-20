---
name: garage-research
description: Conduct thorough garage-side research on a topic and present findings with a clear recommendation — then, if it earns it, hand the result to a board department as an exhibit. Use whenever the CEO asks for research, market/competitive analysis, an investigation into a topic, a comparison of options, or a "should we..." decision that needs evidence. Supports both single-pass deep research and multi-agent independent research where several agents investigate the same question separately and their findings are compared and synthesized into one final breakdown and recommendation. Always trigger this skill's clarification step before starting research, even if the request seems clear — do not skip straight to searching.
---

# Garage Research

A skill for producing thorough, well-sourced research with a clear final
recommendation — done in the garage (ungoverned, ad hoc, costs nothing on
the company's own ledger), with an explicit path to hand the result to the
board when it earns that. See `CLAUDE.md`'s "Two rooms" section for the
garage/board distinction this skill assumes.

## Core principle

Research is only as good as the question it answers. Do not start
searching until the direction is clear. Do not present a recommendation
without showing the reasoning and the confidence level behind it.

---

## Step 0: Clarify direction and scope (always do this first)

**Lead with whatever the CEO already said, not a checklist.** If their
request already answers one of the items below, state your understanding
back in one line and move on — don't re-ask it. Only ask about what's
genuinely still ambiguous, and cap it at a few short questions. The more
they give up front, the less this step should ask.

1. **Subject and boundaries** — What exactly is in scope, and what's
   explicitly out? (e.g. time window, geography, market segment,
   competitor set)
2. **Purpose** — What decision or action will this research inform? (e.g.
   a garage-only "what's out there" look, a directive update, a board
   exhibit headed for a real decision). This determines what "thorough
   enough" means and what the recommendation should optimize for.
3. **Output** — What form should the final deliverable take? (e.g. short
   memo, slide-ready breakdown, decision matrix with scored options)
4. **Mode** — Single-pass deep dive, or multi-agent independent research
   with comparison? (See Step 1.) If the CEO hasn't specified, default to
   single-pass unless the topic is contested, high-stakes, or benefits
   from multiple independent angles — in that case, recommend multi-agent
   and ask for confirmation.

Do not proceed to research until you have a working answer to all four,
even if some are just your own reasonable assumption stated back for a
quick confirm.

---

## Step 1: Choose research mode

### Single-pass mode (default)

One thorough research pass. Use for well-scoped questions where
independent cross-checking isn't necessary.

### Multi-agent independent research mode

Use when the CEO asks for it, or when the topic is contested, high-stakes,
or would benefit from multiple independent angles catching things a single
pass might miss.

**How to run it well — the whole point is genuine independence, not three
copies of the same search:**

- Dispatch N (typically 2–4) agents to investigate the **same core
  question**, but do not let them see each other's work while
  researching. If they share context, you get false consensus, not
  independent verification.
- Give each agent a **distinct angle or source lean** rather than an
  identical prompt, so their disagreements are informative. For example:
  - Agent A: recent news, press, and analyst commentary
  - Agent B: primary sources — official filings, technical docs, direct
    data (e.g. actual shop listings, not summaries of them)
  - Agent C: competitive/comparative landscape
  - Agent D (optional): skeptical/devil's-advocate pass — actively look
    for reasons the obvious answer might be wrong
- Each agent should independently produce: key findings, sources, and its
  own tentative conclusion. Do not have agents pre-negotiate toward a
  middle answer.

---

## Step 2: Compare findings (multi-agent mode only)

Do not just merge the outputs. Explicitly identify:

- **Agreement** — findings all agents converged on independently. This is
  your high-confidence material.
- **Disagreement** — where agents reached different conclusions, cited
  conflicting sources, or had different confidence levels. Show *why*
  they diverged (different sources? different assumptions? different
  framing of the question?) rather than silently averaging or picking
  one.
- **Gaps** — anything only one agent found, or that no agent covered
  well.

If agents materially disagree on a load-bearing fact, say so plainly in
the final output rather than quietly resolving it in the synthesis.

---

## Step 3: Stopping rule (both modes)

Avoid open-ended searching. Stop when:

- The last two or three sources largely confirm existing findings rather
  than add new information, **and**
- The topic is not contested — if it is contested, don't force
  convergence; flag it as contested and present the range of views
  rather than searching indefinitely for a tiebreaker.

If you hit a reasonable search budget without reaching this state, say so
in the output and note what remains uncertain rather than presenting
shaky findings as settled.

---

## Step 4: Present the final output

Structure every final deliverable — single- or multi-agent — as:

1. **Bottom line** — the recommendation, stated plainly, up front.
2. **Confidence** — how confident, and why (strong consensus across
   independent sources vs. thin evidence vs. contested).
3. **Key findings** — the evidence, organized by theme, not by agent.
   Cite sources.
4. **Where reasonable people/agents disagreed** (multi-agent mode) — the
   actual points of divergence and what would resolve them.
5. **What this doesn't cover** — explicit gaps, caveats, or follow-up
   questions the CEO should consider.

Match the output format to what was agreed in Step 0 (memo, matrix,
slide-ready, etc.). Don't default to a generic report format if the CEO
asked for something more specific.

Iterating is normal and expected — landing on a good recommendation often
takes a few rounds (a first pass, a narrower follow-up, a
devil's-advocate check). Keep a running note of what got tried and ruled
out along the way; Step 5 needs it.

---

## Step 5: Garage → Board handoff (Minivan Dads-specific)

Research produced here stays in the garage by default — nothing about
finishing Step 4 requires sending anything to the board. Ask before doing
this step.

1. **Ask whether this should go to the board**, and if so, which
   department and in what form:
   - **One-off exhibit** — the department should read this once, as
     context for its next scheduled/triggered run.
   - **Standing order** — the finding should become part of the
     department's ongoing directive (e.g. `#directive creative ...`),
     because it's not a one-off, it's something the department should
     keep tracking.
   If neither applies, stop here — the garage output stands on its own.

2. **Write the exhibit file** to `garage/research/{slug}-{date}.md`. It
   must contain BOTH pieces, not just the clean answer:
   - The final recommendation, in Step 4's shape (bottom line,
     confidence, findings, disagreements, gaps).
   - **A process/iteration log** — what was tried and ruled out along
     the way, and why. Use the exact convention the board's own reports
     already use for this (see any `hq/reports/{dept}/*.md` with a
     "Killed, and why" section) — a department reading this exhibit
     should recognize the shape as native, not foreign.

3. **On confirmation, promote it into HQ** — call `hq.write_research_exhibit(slug, content)`
   (`brain/hq.py`) rather than writing directly under `hq/` (only
   `hq.py` touches files there — see `CLAUDE.md`'s load-bearing rules).
   This lands at `hq/research/{slug}.md`, git-tracked, and is now a real
   exhibit a department run can ingest via `run_agent(..., exhibit=...)`
   (CLI: `brain agent <dept> --exhibit <slug>`; dashboard:
   `/api/command/agent` with an `exhibit` field).

4. **If it's a standing order instead (or in addition)**, fold a
   condensed reference into the department's directive the same way
   Creative's own backup-handle order was written — cite the exhibit
   by name so the directive stays short and the detail lives in the
   exhibit, not duplicated inline.

---

## Things to avoid

- Skipping Step 0 because the request "seems obvious" — ambiguity here
  wastes the most expensive part of the process (the research itself).
- In multi-agent mode, giving every agent an identical prompt with no
  angle variation — this produces redundant work, not real
  cross-checking.
- Smoothing over disagreement between agents to present a tidier,
  falsely-confident answer.
- Presenting a recommendation without showing the reasoning that
  produced it.
- Searching indefinitely on contested topics instead of flagging them as
  contested.
- Sending something to the board reflexively. Most garage research
  should just stay garage research — see `CLAUDE.md`'s "Two rooms"
  section for when escalation actually earns its cost.
