#!/usr/bin/env python3
"""Advisory PostToolUse hook: hint when an edit under core/ or adapters/
leaves the committed render targets stale (ADR 0085).

Wired project-locally in .claude/settings.json — the render manifest is
hub-specific, so this never ships in the plugin. Advisory by design: always
exits 0; a broken environment reports itself instead of failing the session.
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

WATCHED = ("core/", "adapters/")

RENDER_CMD = "python3 tools/render_core.py --write"


def hint_for(file_path: str, root: Path) -> str | None:
    try:
        rel = Path(file_path).resolve().relative_to(root.resolve())
    except ValueError:
        return None
    if not str(rel).startswith(WATCHED):
        return None
    import render_core
    try:
        problems = (render_core.check(root, render_core.MAPPINGS)
                    + render_core.check_agents(root))
    except ImportError as exc:
        return (f"render drift not checkable ({exc}) — verify manually: "
                "python3 tools/render_core.py --check")
    if not problems:
        return None
    return (f"core/adapters edit left {len(problems)} render finding(s); "
            f"dist/ is what actually ships — run: "
            f"{RENDER_CMD}")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    message = hint_for(file_path, REPO)
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
