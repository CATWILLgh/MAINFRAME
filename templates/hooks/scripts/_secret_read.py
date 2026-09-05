#!/usr/bin/env python3
"""Recognize only standalone ``secret get NAME`` inspection commands."""

from __future__ import annotations

import os
import shlex


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


def decision_reason(command: str) -> str | None:
    if not is_standalone_secret_get(command):
        return None
    return (
        "A standalone `secret get NAME` would expose the credential to the "
        "model. Pass it directly to the process that needs it, for example "
        "`consumer --token \"$(secret get NAME)\"`, without printing, storing, "
        "or describing the value."
    )
