#!/usr/bin/env python3
"""Warn when an actual ripgrep command contains a risky short ``-r`` cluster.

In ripgrep, ``-r`` takes replacement text; it is not grep's recursive flag.
The hook is advisory and silent for every other Bash pattern. It tokenizes
shell commands so quoted examples and arguments to commands such as ``echo``
do not trigger the reminder.
"""

from __future__ import annotations

import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, load_payload, log_hook_signal, run
    from _notice_state import claim_once
except Exception:
    sys.exit(0)


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
SHORT_CLUSTER_RE = re.compile(r"-[A-Za-z]{2,}")
MAX_RENDERED_CLUSTERS = 5
MAX_CLUSTER_CHARS = 24


def _tokenize(command: str) -> list[str] | None:
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
        return " ".join(tokens[index + 1:]) if index + 1 < len(tokens) else None
    for offset, token in enumerate(tokens[index + 1:], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            return tokens[offset + 1] if offset + 1 < len(tokens) else None
    return None


def _risky_clusters_in_rg(tokens: list[str]) -> list[str]:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "rg":
        return []
    risky: list[str] = []
    for token in tokens[index + 1:]:
        if token == "--":
            break
        if SHORT_CLUSTER_RE.fullmatch(token) and "r" in token[1:]:
            risky.append(token)
    return risky


def risky_rg_clusters(command: str, *, depth: int = 0) -> list[str]:
    if depth > 3:
        return []
    tokens = _tokenize(command)
    if tokens is None:
        return []
    findings: list[str] = []
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            findings.extend(risky_rg_clusters(nested, depth=depth + 1))
        else:
            findings.extend(_risky_clusters_in_rg(segment))
    return list(dict.fromkeys(findings))


def main() -> None:
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    clusters = risky_rg_clusters(command)
    if not clusters:
        return
    if not claim_once(
            "rg-replace-cluster", payload.get("session_id"),
            payload.get("agent_id")):
        return
    shown = clusters[:MAX_RENDERED_CLUSTERS]
    rendered = ", ".join(
        f"`{cluster[:MAX_CLUSTER_CHARS]}`" for cluster in shown
    )
    if len(clusters) > MAX_RENDERED_CLUSTERS:
        rendered += f", …and {len(clusters) - MAX_RENDERED_CLUSTERS} more"
    note = (
        "ripgrep option check: " + rendered + " contains `r` in a short "
        "option cluster. In ripgrep, `-r` consumes replacement text and "
        "changes printed matches; it does not enable recursive search and "
        "does not modify files. If replacement is intended, use explicit "
        "`--replace=...`; otherwise remove `r` and write the intended flags "
        "separately."
    )
    emit_note("PreToolUse", note)
    log_hook_signal(
        __file__, "rg-replace-cluster", "noted", len(clusters), payload,
        context=note,
    )


if __name__ == "__main__":
    run(main)
