#!/usr/bin/env python3
"""Warn when an actual ripgrep command uses the ambiguous short ``-r`` form.

In ripgrep, ``-r`` takes replacement text; it is not grep's recursive flag.
The hook is advisory and accepts explicit ``--replace`` without a reminder. It
tokenizes shell commands and follows ripgrep's value-taking option rules so
quoted examples and option values such as ``-g -r`` do not trigger it.
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
MAX_RENDERED_OPTIONS = 5
MAX_OPTION_CHARS = 24


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
        return " ".join(tokens[index + 1 :]) if index + 1 < len(tokens) else None
    for offset, token in enumerate(tokens[index + 1 :], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            return tokens[offset + 1] if offset + 1 < len(tokens) else None
    return None


def _short_option_role(token: str) -> tuple[bool, bool]:
    """Return whether token uses short -r and whether it consumes next argv."""
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


def short_rg_replace_options(command: str, *, depth: int = 0) -> list[str]:
    if depth > 3:
        return []
    tokens = _tokenize(command)
    if tokens is None:
        return []
    findings: list[str] = []
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            findings.extend(short_rg_replace_options(nested, depth=depth + 1))
        else:
            findings.extend(_short_replace_options_in_rg(segment))
    return list(dict.fromkeys(findings))


def main() -> None:
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    options = short_rg_replace_options(command)
    if not options:
        return
    if not claim_once(
        "rg-replace-cluster", payload.get("session_id"), payload.get("agent_id")
    ):
        return
    shown = options[:MAX_RENDERED_OPTIONS]
    rendered = ", ".join(f"`{option[:MAX_OPTION_CHARS]}`" for option in shown)
    if len(options) > MAX_RENDERED_OPTIONS:
        rendered += f", …and {len(options) - MAX_RENDERED_OPTIONS} more"
    note = (
        "ripgrep option check: " + rendered + " uses the short `-r` form. "
        "In ripgrep it changes matched text in the output; recursion is "
        "already the default. Use explicit `--replace=...` when replacement "
        "is intended, otherwise remove `r`. The command was not blocked."
    )
    emit_note("PreToolUse", note)
    log_hook_signal(
        __file__,
        "rg-short-replace",
        "noted",
        len(options),
        payload,
        context=note,
    )


if __name__ == "__main__":
    run(main)
