#!/usr/bin/env python3
"""Allow the test auditor to write only open project tickets."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def decision(kind: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        }
    }


def repository_root(cwd: Path) -> Path:
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ValueError("repository root not found")


def requested_path(payload: dict) -> Path:
    cwd_value = payload.get("cwd")
    file_value = payload.get("tool_input", {}).get("file_path")
    if not isinstance(cwd_value, str) or not cwd_value:
        raise ValueError("missing cwd")
    if not isinstance(file_value, str) or not file_value:
        raise ValueError("missing file path")

    cwd = Path(cwd_value).expanduser().resolve(strict=True)
    raw = Path(os.path.expanduser(file_value))
    return (raw if raw.is_absolute() else cwd / raw).resolve(strict=False)


def is_open_ticket(payload: dict) -> bool:
    cwd = Path(payload["cwd"]).expanduser().resolve(strict=True)
    root = repository_root(cwd)
    allowed = (root / "docs" / "tickets" / "open").resolve(strict=False)
    target = requested_path(payload)
    return os.path.commonpath((str(allowed), str(target))) == str(allowed) and target != allowed


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        allowed = payload.get("tool_name") in {"Write", "Edit"} and is_open_ticket(payload)
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
        allowed = False

    if allowed:
        result = decision("allow", "Test auditor may maintain open project tickets.")
    else:
        result = decision(
            "deny",
            "The test auditor may modify only files below docs/tickets/open/. "
            "Do not modify source code, tests, configuration, or archived tickets; "
            "return any blocked need to the immediate caller.",
        )
    json.dump(result, sys.stdout, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
