#!/usr/bin/env python3
"""Prevent direct secret output and value-bearing registration commands.

This is the canonical, product-agnostic detector for the ``secret-access``
hook. Call :func:`decision_reason` immediately before a shell action. A
returned string is a hard-block reason. ``None`` means that this detector makes
no decision and the receiving product's native permission layer remains
authoritative.

The detector recognizes only direct invocations of the MAINFRAME ``secret``
helper. It is a small guard against common agent mistakes, not a shell parser,
credential sandbox, authorization system, or protected-store access control.
Adapters should protect store paths with native permissions when available.

Adapter requirements:

* pass the exact shell command from the documented pre-action event;
* translate a returned reason into a native hard denial for primary agents and
  subagents;
* emit nothing when the result is ``None``;
* treat malformed input or detector failure as unavailable protection, never
  as evidence that the command is dangerous;
* add no telemetry, persistent state, transcript inspection, or intent
  inference to this file.
"""

from __future__ import annotations

import os
import re
import shlex


SIMPLE_WRAPPERS = {"builtin", "command", "exec"}
SAFE_SET_MODES = {"--clipboard", "--prompt"}
ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def _direct_secret_tokens(command: str) -> list[str] | None:
    if not isinstance(command, str):
        return None
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None

    index = 0
    while index < len(tokens) and ASSIGNMENT_RE.fullmatch(tokens[index]):
        index += 1
    while index < len(tokens) and os.path.basename(tokens[index]) in SIMPLE_WRAPPERS:
        index += 1
    if index >= len(tokens) or os.path.basename(tokens[index]) != "secret":
        return None
    return tokens[index:]


def decision_reason(command: str) -> str | None:
    """Return a hard-block reason for a recognized unsafe direct invocation."""
    tokens = _direct_secret_tokens(command)
    if tokens is None:
        return None

    if len(tokens) == 3 and tokens[1] == "get" and tokens[2]:
        return (
            "A standalone `secret get NAME` would print a credential into the "
            "agent context. Use `secret copy NAME` for the recipient's clipboard "
            "or `secret run NAME -- COMMAND` for process-scoped delivery."
        )

    if len(tokens) >= 4 and tokens[1] == "set" and tokens[2]:
        if len(tokens) == 4 and tokens[3] in SAFE_SET_MODES:
            return None
        return (
            "Passing a credential through `secret set NAME VALUE` exposes it as "
            "a command argument. Copy the value and use `secret set NAME "
            "--clipboard`, or use the protected `--prompt` fallback."
        )

    return None
