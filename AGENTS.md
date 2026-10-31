# AGENTS.md

Instructions for any AI coding agent (Codex, Cursor, Copilot, Claude, etc.) working in this repo.
The canonical rules live in [CLAUDE.md](CLAUDE.md) — read and follow them. Key points:

- Read `docs/PROBLEM.md` and `docs/PLAN.md` before doing anything.
- Only do the task asked. Keep the demo path working.
- Never install dependencies without asking.
- Never read/modify `.env`, `secrets/`, or print environment variables. Never hardcode keys.
- Never push, force-push, hard-reset, or `git clean`. Work on `feat/*` branches.
- Don't modify `.claude/`, `.github/workflows/`, or other agent/CI config.
- Run `python -m pytest -q` and `ruff check .` before claiming work is done.
