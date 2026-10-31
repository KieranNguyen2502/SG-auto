"""PreToolUse guard for Bash/PowerShell. Exit 2 blocks the call and shows stderr to the agent.

Backstop for things permission globs miss (chained commands, flags in odd orders, PowerShell).
"""

import json
import re
import sys

BLOCKED = [
    (r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b", "recursive force delete"),
    (r"Remove-Item\b.*-Recurse", "recursive delete (PowerShell)"),
    (r"\bgit\s+push\b.*(--force|-f\b|--force-with-lease)", "force push"),
    (r"\bgit\s+push\b.*\b(origin\s+)?(main|master)\b", "direct push to main — use a branch + PR"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset"),
    (r"\bgit\s+clean\b", "git clean"),
    (r"\bgit\s+(commit|push)\b.*--no-verify", "skipping hooks"),
    (r"\bgit\s+config\b.*--global", "global git config change"),
    (
        r"(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|iex|python)",
        "piping a download into a shell",
    ),
    (
        r"(^|[\s;&|])(cat|type|less|more|head|tail|Get-Content|gc)\s+[^|;&]*\.env(\s|$|[;&|])",
        "reading .env",
    ),
    (r"\b(printenv|env)\s*($|[;&|])", "dumping environment variables"),
    (r"\bsudo\b", "sudo"),
    (r"\b(mkfs|format\s+[a-z]:|diskpart|shutdown|reboot)\b", "system-level command"),
    (r":\(\)\s*\{", "fork bomb"),
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    for pattern, reason in BLOCKED:
        if re.search(pattern, cmd, re.IGNORECASE):
            print(
                f"Blocked by project guard ({reason}). If this is truly needed, ask the human "
                f"to run it themselves.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
