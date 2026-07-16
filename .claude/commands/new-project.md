---
name: new-project
description: New app project setup — interview the user about their app idea, architecture, and tech stack, then fill out project-context.md, create project-memory.md, and commit both.
---

# New App Project Setup

You are setting up a new app project from scratch.
Your job is to interview the user and use their answers to fill out project-context.md completely.

Do NOT rush. Do NOT move to the next question until the current one is answered clearly.
Do NOT fill in placeholders — every section must have real content before you finish.

---

## 1. Open the kickoff

Say exactly this:

"Let's set up your new app project. I'm going to ask you questions one at a time — take your time with each answer, and I'll ask for more detail if I need it.

What's the idea? What do you want this app to do for you?"

Wait for their answer.
If the answer is vague, ask one follow-up before moving on:
- "Who is this for — just you, or other users too?"
- "What problem does it solve?"
- "What does done look like?"

Do not move to Step 2 until you can write a clear 2–3 sentence project description.

---

## 2. Interview — one question at a time

Ask each question below in order.
Wait for a clear answer before asking the next one.
If an answer is unclear, ask one follow-up question before moving on.

**Q1 — Architecture: Does it need to save data?**
"Does this app need to save data between sessions or between different users?
- No → we'll build a static frontend (HTML/CSS/JS only)
- Yes → we'll need a backend and database
- Not sure yet → that's fine, we'll start static and plan to upgrade

Which fits best?"

Based on their answer, ask the follow-up only if relevant:
"Does this app need to hide any secrets from the browser — like API keys or business logic?
If yes, we'll need a backend even if there's no database."

**Q2 — Tech stack**
"What tools are you planning to use? If you're not sure, say so and I'll suggest a simple starting stack.

- Frontend: (e.g. HTML/CSS/JS, React)
- Backend: (e.g. Node + Express, Python + FastAPI, or none)
- Database: (e.g. Supabase, SQLite, or none)
- Auth: (e.g. Supabase Auth, Clerk, or none)
- Deployment: (e.g. Vercel, Railway, local only)
- AI or external APIs: (e.g. Anthropic API, Stripe, or none)"

**Q3 — User flow**
"Walk me through this app as a user seeing it for the first time.
What's the first screen? What can they do? Where do they go next?
Keep going until the job is done."

If the answer is thin, ask:
"What screens does this app need? Just a simple list."

**Q4 — Data model**
Ask only if the app saves data:
"What are the 'things' in this app and how do they relate?
Example: Users have Projects. Projects have Tasks. Tasks have Comments.
Even one sentence helps."

**Q5 — Current status**
"Where does this project stand right now? Brand new, already started, or picking up something stalled?"

**Q6 — What's built or decided already**
"What exists already — files, decisions, research, a prototype? Or are we starting from zero?"

**Q7 — What's next**
"What are the first 3 things that need to happen to move this forward?"

**Q8 — Tools**
"For each of those tasks — is it thinking and planning (Chat), building and editing files (Claude Code), or browser and desktop work (Cowork)?"

**Q9 — Environment and secrets**
"Do you have any API keys or environment variables this app will need?
Don't share the actual values — just tell me what variables will exist."

**Q10 — Known issues or risks**
"Anything already broken, blocked, or uncertain that I should know going in?
What's the hardest part to build?"

---

## 3. Fill out project-context.md

Using the answers from Step 2, write a complete project-context.md file.
Use this exact template — no placeholders, no empty sections:

```markdown
# Project: [Project Name]
Last updated: [YYYY-MM-DD] by Claude Code

## What this project is
[2–3 sentences — what it is, who it's for, what problem it solves]

## Architecture decision
**Does this app need to save data between sessions or between users?**
- [x] [Chosen option: Static frontend / Full stack / Undecided]

**Does this app need to hide secrets from the browser?**
- [x] [Yes / No]

**Current answer:** [Static frontend / Full stack / Undecided]

## Tech stack
| Layer | Tool/Language | Notes |
|---|---|---|
| Frontend | [value] | |
| Backend | [value or none] | |
| Database | [value or none] | |
| Auth | [value or none] | |
| Deployment | [value] | |
| AI / APIs | [value or none] | |

## Data model
[From Q4, or "Not applicable — static frontend"]

## User flow
[From Q3 — the path a user takes through the app start to finish]

## Current status
[One paragraph — what stage, what exists, what's not built yet]

## Where we left off
Last commit: N/A
In progress: Project setup — first session
Branch: main

## What's next
- [ ] [Task 1 — Tool]
- [ ] [Task 2 — Tool]
- [ ] [Task 3 — Tool]

## File structure
```
/project-root
  /src        → [what lives here]
  /assets     → [what lives here]
  /docs       → reference guides
  /archive    → archived context docs
  index.html  → [what this is]
```

## Environment and credentials
- .env file: [exists / not yet created]
- Variables needed: [list from Q9, or "none"]
- Where secrets are stored: [local .env / Vercel dashboard / not set up yet]

## Key decisions made
- [YYYY-MM-DD] — Project initialized
- [YYYY-MM-DD] — Architecture: [Static frontend / Full stack]

## Known issues
[From Q10, or "None at this time"]

## Context for each tool

### Chat
Thinking, planning, decisions, and fuzzy problems.
Flag architecture changes or scope changes before acting.

### Claude Code
Building and editing files. Tech stack: [summary from Q2].
Run /start-of-day at the start of every session.
Run /end-of-day at the end of every session.

### Cowork
Browser tasks, desktop automation, file management.
Use project-context-updater.html on Cowork-heavy days.

## Change log
- [YYYY-MM-DD] — Project initialized — Source: Claude Code
```

Show the completed file to the user and say:
"Here's your project-context.md — does this look right? Anything to change before I save it?"

Wait for confirmation. Make any changes requested before saving.

---

## 4. Create project-memory.md

Write the following file to the project root:

```markdown
# Project Memory
Last updated: [YYYY-MM-DD]

This file captures decisions, reasoning, and session context that
project-context.md doesn't hold. It is Claude's memory between sessions.

---

## Key decisions (permanent record)

- [YYYY-MM-DD] — Project initialized
- [YYYY-MM-DD] — Architecture decision: [Static frontend / Full stack]

---

## Sessions

<!-- end-of-day skill appends new sessions here -->
```

---

## 5. Save both files

```bash
git add project-context.md project-memory.md
git commit -m "New app project initialized — [Project Name]"
```

---

## 6. Done

Tell the user:

"Your app project is set up and committed.

From here:
- Start every session with /start-of-day
- End every session with /end-of-day
- Use Chat for architecture decisions and planning

What are we working on in this first session?"
