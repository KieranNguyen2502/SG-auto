---
description: Ingest the hackathon problem statement and produce a plan
argument-hint: [paste problem statement or path to file]
---

The hackathon problem statement is below (or at the path given). Do the following, in order:

1. Write it verbatim into `docs/PROBLEM.md` under "## Raw statement", then fill in the
   structured sections (requirements, judging criteria, constraints, deliverables, deadline).
2. Use the `planner` subagent to produce a plan, and write it to `docs/PLAN.md`.
3. Propose a tech stack in `docs/DECISIONS.md` (one short entry, with why). If it changes the
   default Python setup, list the exact dependency changes but **do not install anything** —
   ask me first.
4. Stop and summarize: the MVP slice, top 3 risks, and the first task you'd start on.

Problem statement:
$ARGUMENTS
