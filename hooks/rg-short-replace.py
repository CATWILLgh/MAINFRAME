#!/usr/bin/env python3
"""Advise when ripgrep's short ``-r`` replacement option is used.

Call :func:`advisory_message` immediately before a shell action. A returned
message is bounded non-blocking context. ``None`` means silence. The detector
parses actual command positions, option values, shell segments, and a small set
of nested shell forms so quoted examples and unrelated arguments stay quiet.

This canonical source has no product payload, output schema, state, telemetry,
or installation logic. The adapter owns native event mapping and duplicate
delivery suppression for the same event identity. Malformed input and detector
failure never block the shell action.
"""

from __future__ import annotations

import os
import re
import shlex


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
SHORT_VALUE_OPTIONS = frozenset("efEmjgdtTABCMr")
LONG_VALUE_OPTIONS = frozenset(
    {
        "--after-context",
        "--before-context",
        "--color",
        "--colors",
        "--context",
        "--context-separator",
        "--dfa-size-limit",
        "--encoding",
        "--engine",
        "--field-context-separator",
        "--field-match-separator",
        "--file",
        "--generate",
        "--glob",
        "--hostname-bin",
        "--hyperlink-format",
        "--iglob",
        "--ignore-file",
        "--max-columns",
        "--max-count",
        "--max-depth",
        "--max-filesize",
        "--path-separator",
        "--pre",
        "--pre-glob",
        "--regex-size-limit",
        "--regexp",
        "--replace",
        "--sort",
        "--sortr",
        "--threads",
        "--type",
        "--type-add",
        "--type-clear",
        "--type-not",
    }
)
MAX_NESTED_DEPTH = 3


def _tokenize(command: str) -> list[str] | None:
    if not isinstance(command, str):
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in OPERATORS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _is_assignment(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token))


def _command_index(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    while index < len(tokens) and os.path.basename(tokens[index]) in SIMPLE_WRAPPERS:
        index += 1
    return index


def _nested_command(tokens: list[str]) -> str | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) not in SHELLS:
        return None
    if os.path.basename(tokens[index]) == "eval":
        return " ".join(tokens[index + 1 :]) if index + 1 < len(tokens) else None
    for offset, token in enumerate(tokens[index + 1 :], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            return tokens[offset + 1] if offset + 1 < len(tokens) else None
    return None


def _short_option_role(token: str) -> tuple[bool, bool]:
    """Return whether a short option uses ``-r`` and consumes the next argv."""
    if token == "-" or not token.startswith("-") or token.startswith("--"):
        return False, False
    cluster = token[1:]
    for index, option in enumerate(cluster):
        if option not in SHORT_VALUE_OPTIONS:
            continue
        consumes_next = index == len(cluster) - 1
        return option == "r", consumes_next
    return False, False


def _short_replace_options_in_rg(tokens: list[str]) -> list[str]:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "rg":
        return []
    risky: list[str] = []
    index += 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            break
        if token.startswith("--"):
            option = token.split("=", 1)[0]
            if option in LONG_VALUE_OPTIONS and "=" not in token:
                index += 2
            else:
                index += 1
            continue
        uses_replace, consumes_next = _short_option_role(token)
        if uses_replace:
            risky.append(token)
        index += 2 if consumes_next else 1
    return risky


def short_replace_options(command: str, *, depth: int = 0) -> list[str]:
    """Return ambiguous short replacement option tokens from actual rg calls."""
    if depth > MAX_NESTED_DEPTH:
        return []
    tokens = _tokenize(command)
    if tokens is None:
        return []
    findings: list[str] = []
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            findings.extend(short_replace_options(nested, depth=depth + 1))
        else:
            findings.extend(_short_replace_options_in_rg(segment))
    return list(dict.fromkeys(findings))


def advisory_message(command: str) -> str | None:
    """Return bounded correction context, or ``None`` when no issue is found."""
    if not short_replace_options(command):
        return None
    return (
        "ripgrep option check: short `-r` replaces matched output; recursion is "
        "already the default. Use explicit `--replace=...` when replacement is "
        "intended, otherwise remove `r`. The command was not blocked."
    )
