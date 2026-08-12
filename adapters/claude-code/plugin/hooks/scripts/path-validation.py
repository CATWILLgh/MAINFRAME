#!/usr/bin/env python3
"""Require confirmation for risky or unresolved recursive ``rm`` targets.

This global PreToolUse hook is only a destructive-path circuit breaker. A
plain recursive removal whose literal target resolves strictly below the
project root produces no decision, so Claude Code's normal permission flow
still applies. The hook never returns ``allow``.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import log_hook_signal
except Exception:
    log_hook_signal = None


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
CWD_COMMANDS = {"cd", "pushd", "popd"}
SHELL_COMMANDS = {"sh", "bash", "zsh", "dash", "ksh"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
RUNTIME_WRAPPERS = {"sudo", "doas", "env", "timeout", "nice", "stdbuf"}
SHELL_META_RE = re.compile(r"\$|`|[?*\[]|[{}]|<\(|>\(")
RM_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?rm(?=\s|$)")


def emit_ask(reason: str, payload: dict | None = None) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    if log_hook_signal is not None:
        log_hook_signal(
            __file__, "recursive-delete", "asked", 1, payload or {},
            context=reason,
        )


def tokenize(command: str) -> list[str] | None:
    """Tokenize operators while preserving operators inside quoted words."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def split_subcommands(tokens: list[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in OPERATORS:
            if current:
                result.append(current)
                current = []
        else:
            current.append(token)
    if current:
        result.append(current)
    return result


def _basename(token: str) -> str:
    return os.path.basename(token)


def _is_assignment(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token))


def _recursive_rm_at(tokens: list[str], index: int) -> bool:
    if index >= len(tokens) or _basename(tokens[index]) != "rm":
        return False
    for token in tokens[index + 1:]:
        if token == "--":
            return False
        if token == "--recursive":
            return True
        if token.startswith("-") and not token.startswith("--"):
            if "r" in token[1:] or "R" in token[1:]:
                return True
    return False


def _direct_rm_index(tokens: list[str]) -> int | None:
    """Locate rm only where it can be the command, not an echo argument."""
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    while index < len(tokens) and _basename(tokens[index]) in SIMPLE_WRAPPERS:
        index += 1
    if index < len(tokens) and _basename(tokens[index]) == "rm":
        return index
    if index < len(tokens) and _basename(tokens[index]) in RUNTIME_WRAPPERS:
        candidate = _wrapped_command_index(tokens, index)
        if candidate is not None and _basename(tokens[candidate]) == "rm":
            return candidate
    return None


def _wrapped_command_index(tokens: list[str], index: int) -> int | None:
    """Best-effort command position for the small supported wrapper set."""
    wrapper = _basename(tokens[index])
    cursor = index + 1
    options_with_value = {
        "sudo": {"-u", "-g", "-h", "-p", "-C", "-T", "--user", "--group"},
        "doas": {"-u"},
        "timeout": {"-k", "-s", "--kill-after", "--signal"},
        "nice": {"-n", "--adjustment"},
        "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    }.get(wrapper, set())
    while cursor < len(tokens) and tokens[cursor].startswith("-"):
        option = tokens[cursor].split("=", 1)[0]
        cursor += 1
        if option in options_with_value and "=" not in tokens[cursor - 1]:
            cursor += 1
    if wrapper == "env":
        while cursor < len(tokens) and _is_assignment(tokens[cursor]):
            cursor += 1
    elif wrapper == "timeout":
        # The duration is the final wrapper argument before the command.
        cursor += 1
    return cursor if cursor < len(tokens) else None


def _paths_after_rm(tokens: list[str], index: int) -> list[str]:
    paths: list[str] = []
    after_separator = False
    for token in tokens[index + 1:]:
        if after_separator:
            paths.append(token)
        elif token == "--":
            after_separator = True
        elif not token.startswith("-"):
            paths.append(token)
    return paths


def _nested_shell_command(tokens: list[str]) -> str | None:
    if not tokens or _basename(tokens[0]) not in SHELL_COMMANDS | {"eval"}:
        return None
    if _basename(tokens[0]) == "eval":
        return " ".join(tokens[1:]) if len(tokens) > 1 else None
    for index, token in enumerate(tokens[1:], 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            return tokens[index + 1] if index + 1 < len(tokens) else None
    return None


def _dynamic_rm(tokens: list[str]) -> bool:
    """True for xargs/find forms whose targets come from runtime input."""
    if not tokens:
        return False
    command = _basename(tokens[0])
    if command == "xargs":
        return any(_recursive_rm_at(tokens, i) for i in range(1, len(tokens)))
    if command == "find":
        return any(
            tokens[i - 1] in {"-exec", "-execdir"} and _recursive_rm_at(tokens, i)
            for i in range(1, len(tokens))
        )
    return False


def _target_reason(path: str, cwd: str, project_dir: str) -> str | None:
    if SHELL_META_RE.search(path):
        return f"recursive rm target requires shell expansion: {path[:100]}"
    absolute = path if os.path.isabs(path) else os.path.join(cwd, path)
    resolved = os.path.realpath(os.path.expanduser(absolute))
    project = os.path.realpath(project_dir)
    if resolved == project:
        return f"recursive rm targets the project root: {project}"
    try:
        inside = os.path.commonpath([resolved, project]) == project
    except ValueError:
        inside = False
    if not inside:
        return f"recursive rm target is outside the project: {resolved}"
    return None


def decision_reason(
    command: str, cwd: str, project_dir: str, *, depth: int = 0,
) -> str | None:
    """Return an ask reason, or None to leave normal permissions unchanged."""
    if not command or RM_HINT_RE.search(command) is None:
        return None
    if "<(" in command or ">(" in command:
        return "recursive rm target requires shell expansion"
    if depth > 3:
        return "recursive rm is nested too deeply to validate safely"
    tokens = tokenize(command)
    if tokens is None:
        return "recursive rm command could not be parsed safely"

    cwd_may_have_changed = False
    for segment in split_subcommands(tokens):
        nested = _nested_shell_command(segment)
        if nested is not None and RM_HINT_RE.search(nested):
            reason = decision_reason(nested, cwd, project_dir, depth=depth + 1)
            return reason or "recursive rm is executed through a nested shell"

        if _dynamic_rm(segment):
            return "recursive rm receives targets dynamically from xargs or find"

        index = _direct_rm_index(segment)
        if index is not None and _recursive_rm_at(segment, index):
            if cwd_may_have_changed:
                return "recursive rm follows a shell directory change"
            paths = _paths_after_rm(segment, index)
            if not paths:
                return "recursive rm has no explicit target"
            for path in paths:
                reason = _target_reason(path, cwd, project_dir)
                if reason:
                    return reason

        if segment and _basename(segment[0]) in CWD_COMMANDS:
            cwd_may_have_changed = True

    # A hint that could not be classified as an executable rm (for example an
    # echoed command) is ignored. A classified safe rm deliberately returns no
    # decision rather than allow, preserving Claude Code's permission flow.
    return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cwd = payload.get("cwd") or project_dir
    reason = decision_reason(command, cwd, project_dir)
    if reason:
        emit_ask(reason, payload)


if __name__ == "__main__":
    main()
