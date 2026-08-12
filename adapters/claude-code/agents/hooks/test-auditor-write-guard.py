#!/usr/bin/env python3
"""Allow the test auditor to write only open project tickets."""

from __future__ import annotations

import json
import os
import shlex
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


def requested_path(payload: dict, file_value: str | None = None) -> Path:
    cwd_value = payload.get("cwd")
    if file_value is None:
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


def ticket_move_paths(command: str) -> tuple[str, str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError as error:
        if "mv" in command:
            raise ValueError("ambiguous mv command") from error
        return None
    if not any(Path(token).name == "mv" for token in tokens):
        return None
    if any(token in {"&&", "||", ";", "|", "|&", "&", "(", ")"} for token in tokens):
        raise ValueError("compound mv command")
    while tokens and ("=" in tokens[0] and not tokens[0].startswith("=")):
        name, _, _ = tokens[0].partition("=")
        if not name.replace("_", "a").isalnum() or name[0].isdigit():
            break
        tokens.pop(0)
    if tokens and Path(tokens[0]).name in {"command", "exec"}:
        tokens.pop(0)
    if not tokens or Path(tokens[0]).name != "mv":
        raise ValueError("nested mv command")
    operands = [token for token in tokens[1:] if token == "--" or not token.startswith("-")]
    operands = [token for token in operands if token != "--"]
    if len(operands) != 2:
        raise ValueError("mv must have one source and one destination")
    return operands[0], operands[1]


def is_open_ticket_move(payload: dict) -> bool | None:
    command = payload.get("tool_input", {}).get("command")
    if not isinstance(command, str) or not command:
        raise ValueError("missing command")
    paths = ticket_move_paths(command)
    if paths is None:
        return None
    source, destination = paths
    if not source.endswith(".md") or not destination.endswith(".md"):
        return False
    return all(
        is_open_ticket({**payload, "tool_input": {"file_path": path}})
        for path in paths
    )


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else "write"
    try:
        payload = json.load(sys.stdin)
        if mode == "ticket-move":
            if payload.get("tool_name") != "Bash":
                raise ValueError("wrong tool")
            allowed = is_open_ticket_move(payload)
            if allowed is None:
                return 0
        elif mode == "write":
            allowed = payload.get("tool_name") in {"Write", "Edit"} and is_open_ticket(payload)
        else:
            raise ValueError("unknown mode")
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
        allowed = False

    if allowed:
        reason = (
            "Test auditor may move an open project ticket."
            if mode == "ticket-move"
            else "Test auditor may maintain open project tickets."
        )
        result = decision("allow", reason)
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
