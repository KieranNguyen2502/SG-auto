"""PreToolUse guard for file edits. Exit 2 blocks the edit and shows stderr to the agent."""

import json
import re
import sys
from pathlib import PurePath

PROTECTED = [
    (r"(^|/)\.env($|\.(?!example$)[^/]*$)", "secrets file (.env*) — edit .env.example instead"),
    (r"(^|/)secrets/", "secrets directory"),
    (r"(^|/)\.git/", "git internals"),
    (r"(^|/)\.claude/(settings\.json|hooks/)", "agent guardrails — ask the human to change these"),
    (r"(^|/)\.github/workflows/", "CI config — ask the human first"),
    (r"\.(pem|key|p12|pfx)$", "private key / certificate"),
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    norm = PurePath(path).as_posix()
    for pattern, reason in PROTECTED:
        if re.search(pattern, norm, re.IGNORECASE):
            print(f"Blocked edit to {path}: {reason}.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
