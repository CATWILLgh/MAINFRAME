#!/usr/bin/env python3
"""SessionStart check for shared hook imports and deferred failures."""

import json
import os
import sys


def _state_root():
    return os.environ.get(
        "MAINFRAME_HOOK_FAILURE_STATE_DIR",
        os.path.expanduser("~/.claude/mainframe/state/hook-failures"),
    )


def _claim_pending():
    """Atomically claim pending notices so parallel starts report them once."""
    root = _state_root()
    try:
        names = [name for name in os.listdir(root) if name.endswith(".json")]
    except FileNotFoundError:
        return []
    messages = []
    for name in sorted(names):
        source = os.path.join(root, name)
        claim = source + f".claim-{os.getpid()}"
        try:
            os.replace(source, claim)
        except FileNotFoundError:
            continue
        try:
            with open(claim, encoding="utf-8") as handle:
                value = json.load(handle)
            message = value.get("message") if isinstance(value, dict) else None
            if isinstance(message, str) and message:
                messages.append(message)
        finally:
            try:
                os.unlink(claim)
            except FileNotFoundError:
                pass
    return messages


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    notices = _claim_pending()
    broken = []
    for module in ("_hooklib", "_markers"):
        try:
            __import__(module)
        except Exception as exc:
            broken.append(f"{module} ({type(exc).__name__}: {exc})")
    if broken:
        notices.append(
            "MAINFRAME hook failure: shared hook modules could not be loaded: "
            f"{'; '.join(broken)}. Checks depending on them are unavailable. "
            "Report this failure to the user before claiming hook-backed "
            "verification. Do not repair MAINFRAME unless assigned."
        )
    if not notices:
        return
    text = "\n".join(notices)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        },
        "systemMessage": text,
    }))


if __name__ == "__main__":
    main()
