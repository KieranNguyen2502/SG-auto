# CLAUDE.md

Hackathon project. The problem statement may not be out yet — check `docs/PROBLEM.md` first.
If it's still TBD, don't build features; only improve the baseline when asked.

## Source of truth
- `docs/PROBLEM.md` — what we're building and how it's judged.
- `docs/PLAN.md` — ordered tasks. Work on the next unchecked task unless told otherwise.
- `docs/DECISIONS.md` — settled choices. Don't relitigate them; append new ones.

## Commands
```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
python -m pytest -q             # tests
ruff check . && ruff format .   # lint + format
python -m app.main              # run
```

## Layout
- `src/app/` — application code
- `tests/` — pytest tests (no network; mock external APIs)
- `docs/` — problem, plan, decisions

## Working rules
- **Scope:** do only the task asked. No drive-by refactors, no new features "while you're there".
- **Demo first:** keep the end-to-end demo path working at every commit. Prefer simple and working
  over clever and half-done.
- **Dependencies:** never install or add a package without asking. Say what and why.
- **Secrets:** never read `.env` or `secrets/`, never hardcode keys, never print env vars. Load config
  via environment variables; document new ones in `.env.example`.
- **Git:** work on `feat/*` branches. Commit small and often. Never push, force-push, hard-reset,
  or rewrite history — the human pushes.
- **Tests:** new logic gets a test. Run tests before saying something works; report failures honestly.
- **Protected (hooks will block edits):** `.env*`, `secrets/`, `.claude/settings.json`,
  `.claude/hooks/`, `.github/workflows/`. Ask the human to change these.
- **Unsure?** Ask one concrete question rather than guessing on requirements.

## Agents & commands
- `/kickoff <statement>` — ingest problem statement → PROBLEM.md, PLAN.md, stack proposal.
- `/checkpoint` — lint, test, review, commit on a branch.
- Subagents: `planner` (read-only planning), `reviewer` (read-only review), `tester` (tests/ only).
