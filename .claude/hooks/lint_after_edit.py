"""PostToolUse: auto-format edited Python files and feed remaining lint errors back to the agent.

No-op if ruff isn't installed or the file isn't Python. Exit 2 = agent sees stderr and should fix.
"""

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = (data.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0
    ruff = shutil.which("ruff")
    cmd = [ruff] if ruff else [sys.executable, "-m", "ruff"]
    try:
        subprocess.run([*cmd, "format", path], capture_output=True, timeout=30)
        result = subprocess.run(
            [*cmd, "check", "--fix", path], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if result.returncode == 0:
        return 0
    if "No module named ruff" in result.stderr:
        return 0
    print(f"ruff found issues in {path}:\n{result.stdout}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
