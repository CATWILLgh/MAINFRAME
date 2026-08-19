#!/usr/bin/env python3
"""Block only a standalone ``secret get NAME`` inspection command."""

from __future__ import annotations

import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_permission, load_payload, log_hook_signal
except Exception:
    sys.exit(0)


def is_standalone_secret_get(command: str) -> bool:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if tokens[:1] == ["command"]:
        tokens = tokens[1:]
    return (
        len(tokens) == 3
        and os.path.basename(tokens[0]) == "secret"
        and tokens[1] == "get"
        and bool(tokens[2])
    )


def main() -> None:
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not is_standalone_secret_get(command):
        return
    reason = (
        "A standalone `secret get NAME` would expose the credential to the "
        "model. Pass it directly to the process that needs it, for example "
        "`consumer --token \"$(secret get NAME)\"`, without printing, storing, "
        "or describing the value."
    )
    emit_permission("deny", reason)
    log_hook_signal(
        os.path.basename(__file__), "standalone-secret-read", "blocked", 1,
        payload, context=reason,
    )


if __name__ == "__main__":
    main()
