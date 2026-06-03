#!/usr/bin/env python3
"""PostToolUse authoring check (hub-dev only, project settings): when
`_hooklib.py` or `_markers.py` is edited, verify it still imports.

Catches a broken shared lib at authoring time — the tightest loop — before it
silently disables every hook that depends on it. The SessionStart smoke-check in
the plugin is the runtime backstop; this is the on-edit one. Self-contained;
fail-safe.
"""

import json
import os
import sys

WATCHED = {"_hooklib.py", "_markers.py"}


def main():
    payload = json.load(sys.stdin)
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if os.path.basename(file_path) not in WATCHED:
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(file_path)))
    broken = []
    for mod in ("_hooklib", "_markers"):
        try:
            sys.modules.pop(mod, None)  # re-import the just-saved source, not a cached copy
            __import__(mod)
        except Exception as exc:
            broken.append(f"{mod} ({type(exc).__name__}: {exc})")
    if not broken:
        return
    note = (
        f"Shared hook lib is now broken: {'; '.join(broken)}. Every hook importing "
        "it silently no-ops until fixed. Resolve before declaring the task done."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note}
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
