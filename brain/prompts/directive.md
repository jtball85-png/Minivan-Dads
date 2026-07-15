# Command: directive

The CEO wants to create or revise one department's standing directive. The
department's current directive and the CEO's requested changes are in the
user message.

Produce the COMPLETE new directive file content, wrapped in a fenced code
block (```markdown ... ```), with the full structure: title,
"Last updated: {today}", Tier, Status, Mandate, Boundaries, Report cadence,
Standing orders. It replaces the old file wholesale — never a partial diff.

Validate the requested changes before drafting:

- Check them against the charter (mission, voice, pillars, guardrails) and
  the tier definitions. If a requested standing order exceeds what the
  department's declared tier permits — e.g. asking a Tier 0 department to
  publish, or a Tier 1 department to spend — say so plainly and either
  scope the order down to fit the tier or flag it.
- Tier changes are board decisions, never directive edits. If the CEO's
  request amounts to changing the department's tier (raising OR lowering),
  do NOT draft the promotion into the directive. Instead, include the
  literal marker [REQUIRES BOARD DECISION] in your response, explain why,
  and draft the directive at the department's CURRENT tier.
- If any requested order touches money, brand identity, legal, or
  irreversible actions, the directive text must route that action through
  CEO approval explicitly, whatever the tier.

Before the fenced block, give a short summary of what changed and anything
you scoped down or flagged. After the block, nothing.
