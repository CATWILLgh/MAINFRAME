"""Minimal subprocess environment for packaged release tests."""

from __future__ import annotations

import os


PASSTHROUGH_ENVIRONMENT = (
    "PATH",
    "TMPDIR",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "COLORTERM",
)


def isolated_environment(**overrides: str) -> dict[str, str]:
    environment = {
        name: os.environ[name]
        for name in PASSTHROUGH_ENVIRONMENT
        if name in os.environ
    }
    environment.update(overrides)
    return environment
