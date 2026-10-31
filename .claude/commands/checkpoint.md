---
description: Lint, test, review, and commit the current work on a feature branch
---

1. Run `ruff check .`, `ruff format --check .`, and `python -m pytest -q`. Fix failures caused by
   our changes; report anything else.
2. Use the `reviewer` subagent on the diff and address any real bugs it finds.
3. If on `main`, create a branch `feat/<short-name>` first.
4. Commit with a clear message. Update the task checkboxes in `docs/PLAN.md`.
5. Do not push — tell me it's ready and I'll push.
