---
name: start-of-day
description: Start of session orientation — read project-context.md and project-memory.md, confirm understanding, and ask what we're working on today.
---

# Start of Day — Session Orientation

Execute these steps in exact order.
Do NOT skip steps.
Do NOT begin working until all steps are complete.

---

## 1. Read both context files

Read the following files from the project root:

```bash
cat project-context.md
cat project-memory.md
```

If either file is missing, stop and tell the user:
- "project-context.md not found — please paste it directly into the chat."
- "project-memory.md not found — this may be a new project. Run /new-project to initialize."

---

## 2. Confirm orientation

After reading both files, give the user a short orientation summary in this exact format:

---
**Project:** [project name from project-context.md]
**Last updated:** [date from project-context.md]
**Architecture:** [Static frontend / Full stack — from architecture decision section]
**Tech stack:** [one line summary from tech stack table]
**Where we left off:** [1–2 sentences from the "Where we left off" section]
**What's next:** [list the open tasks from "What's next"]
**Last session memory:** [1–2 sentences summarizing the most recent entry in project-memory.md]
---

Keep it short. Facts only. No interpretation.

---

## 3. Ask what we're working on today

After the summary, ask exactly this:

"What are we working on today — sticking with What's Next, or something different?"

Wait for the user's answer before doing anything else.

---

## 4. Begin

Once the user confirms the focus for today, acknowledge it in one sentence and begin.

Do not re-summarize. Do not ask follow-up questions. Just start.
