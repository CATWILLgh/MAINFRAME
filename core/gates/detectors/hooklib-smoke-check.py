#!/usr/bin/env python3
"""SessionStart smoke-check: verify the shared hook library imports.

If `_hooklib` or `_markers` fails to import, every hook that depends on them
silently no-ops (each guards its own import -> exit 0). That silence is only safe
if the off-state is announced ONCE at a chokepoint — this hook is that chokepoint.
On a failed import it emits a LOUD note naming the disabled gates.

Deliberately self-contained: it must NOT import the library it is verifying, so
it uses only json/os/sys and its own fail-safe.
"""

import json
import os
import sys


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    broken = []
    for mod in ("_hooklib", "_markers"):
        try:
            __import__(mod)
        except Exception as exc:
            broken.append(f"{mod} ({type(exc).__name__}: {exc})")
    if not broken:
        return
    note = (
        "MAINFRAME hub: shared hook library failed to import — "
        f"{'; '.join(broken)}. The suppression-marker and debug-residue gates "
        "(and any hook sharing _hooklib) are SILENTLY DISABLED until this is "
        "fixed in the hub's core/gates/detectors/ (rendered to "
        "dist/claude-code/plugin/hooks/scripts/). Fix the core module, re-render, then "
        "start a new session to re-enable the gates."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note}
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
