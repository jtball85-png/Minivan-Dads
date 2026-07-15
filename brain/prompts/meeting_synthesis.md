# Command: meeting synthesis

The board meeting just ended. You have the agenda and the CEO's rulings on
each item in the user message. Turn them into the meeting's permanent
records. Output exactly these four sections, with these exact headings, in
this order — code splits your output on them:

## Minutes

A readable narrative record of the meeting: what was discussed, what was
ruled, notable CEO reasoning. Written for a future reader (or agent)
reconstructing why things happened. Include items that were skipped or
rejected — the record of what was NOT approved matters as much as what was.

## Decision Log Entries

One block per ruling that produced an actual decision (approved or
modified items; rejected proposals are logged too, as "Rejected: ..."
decisions, since a veto is a decision). Skipped items produce no entry.
Each block in exactly this shape:

### <one-line decision title>
- Rationale: <why, reflecting the CEO's stated reasoning where given>
- Decided by: <"CEO" for CEO REQUIRED items and any modified/rejected
  ruling; "brain (ratified at board meeting)" for BRAIN DECIDES items
  approved as proposed>
- Affected departments: <comma-separated, or "none">

## Directive Updates

One subsection per department whose standing orders changed as a result of
this meeting. If no directives changed, write exactly "None." and nothing
else. Each subsection:

### {department}

The COMPLETE new directive file content, wrapped in a fenced code block
(```markdown ... ```). It replaces the old file wholesale — include the
full structure: title, "Last updated: {today}", Tier, Status, Mandate,
Boundaries, Report cadence, Standing orders. Never emit a partial diff.
The fence is required: code extracts the directive from inside it.

## Resolved Escalations

One line per escalation resolved by a ruling in this meeting:
`{ESC-ID}: <resolution text>`

If none were resolved, write exactly "None."
