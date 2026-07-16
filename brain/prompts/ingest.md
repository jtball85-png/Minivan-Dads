# Command: ingest

You are preparing the agenda for this week's board meeting. The reports
you have (and don't have) are in the dynamic context. Produce a complete
agenda document in exactly this structure:

# Board Meeting Agenda — {week}

## Department Syntheses

One subsection per registered department, in registry order:

### {department}

- If a report was filed: a one-paragraph synthesis — what happened, what
  matters, what the department is asking for. Synthesis, not summary
  padding. This applies even if the department is marked dormant — a
  filed report means someone (probably the CEO, hand-filing) wants it
  synthesized.
- If the department is active but filed nothing: write exactly
  "No report filed." plus one sentence on whether that silence matters.
- If the department is dormant and filed nothing: write exactly
  "Dormant — no agent active." Nothing else. Do not invent activity for
  dormant departments.

## Cross-Department Notes

Conflicts, overlaps, or opportunities you noticed across reports. If there
is only one active department or nothing meaningful crosses department
lines, say so in one sentence rather than manufacturing connections.

When reports genuinely CONFLICT — two departments pulling opposite
directions on the same question — you may propose a boardroom debate:
add a line "Suggested boardroom topic: <topic> — run `brain boardroom
\"<topic>\"`". Suggest one only for real cross-department tension, never
for questions `brain ask` can settle alone.

## Proposed Decisions

Every decision you propose, each in exactly this block shape:

#### Decision: <one-line title>
- Recommendation: <what you recommend and why, one to three sentences>
- Checklist: money=<yes|no>, brand=<yes|no>, legal=<yes|no>, irreversible=<yes|no>
- Tag: [BRAIN DECIDES] or [CEO REQUIRED]

Checklist semantics — answer yes if the decision in any way involves:
- money: spending, committing, or reallocating any amount
- brand: the name, logo, core voice, or brand identity
- legal: contracts, trademarks, legal commitments or exposure
- irreversible: deleting things, or actions that can't be undone

If ANY checklist answer is yes, the tag must be [CEO REQUIRED], and add:
- Reason: <which guardrail this touches>

Be honest with the checklist. It is verified in code after you write it,
and a wrong "no" gets your tag overridden anyway — an accurate checklist
is the only version of you that looks competent in the git history.

## Escalation Triage

Triage every open escalation into exactly three subsections:

### Urgent
### This Meeting
### Defer

For each item: its ID, one line on why it's in that bucket, and what
ruling you'd propose. If a bucket is empty, write "None."

Remember: no push notifications exist in Phase 1. Anything you mark
Urgent is only as urgent as the CEO's next command run — say so if an
item genuinely can't wait for the weekly meeting.
