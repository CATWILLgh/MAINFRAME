#!/usr/bin/env python3
"""Project shared detector fallbacks into one adapter-owned runtime."""

from __future__ import annotations

from pathlib import Path


FEEDBACK_FALLBACK = 'os.path.expanduser("~/.claude/skills/harness-feedback")'
TELEMETRY_FALLBACK = (
    'os.path.expanduser("~/.claude/mainframe/telemetry/telemetry.db")'
)


def project_hooklib_fallbacks(
    text: str,
    source: Path,
    *,
    feedback: str,
    telemetry: str,
) -> str:
    text = _replace_once(text, FEEDBACK_FALLBACK, feedback, source)
    return _replace_once(text, TELEMETRY_FALLBACK, telemetry, source)


def _replace_once(text: str, needle: str, replacement: str, source: Path) -> str:
    count = text.count(needle)
    if count != 1:
        raise ValueError(f"{source}: expected one projection anchor, found {count}")
    return text.replace(needle, replacement)
