#!/usr/bin/env python3
"""Block recursive ``rm`` only for three catastrophic literal targets.

The active Codex permission mode owns every narrower or unresolved command.
MAINFRAME intervenes only when a target resolves exactly to the filesystem
root, the user's home root, or the active project root. The hook never returns
``allow`` and does not treat leaving the project as unsafe by itself.
"""

from __future__ import annotations

import os
import re
import shlex


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SHELL_COMMANDS = {"sh", "bash", "zsh", "dash", "ksh"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
RUNTIME_WRAPPERS = {"sudo", "doas", "env", "timeout", "nice", "stdbuf"}
RM_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?rm(?=\s|$)")


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


def _target_reason(path: str, cwd: str, project_dir: str) -> str | None:
    home = os.path.realpath(os.path.expanduser("~"))
    if path in {"$HOME", "${HOME}"}:
        resolved = home
    elif "$" in path or "`" in path or any(char in path for char in "?*[]{}"):
        return None
    else:
        absolute = path if os.path.isabs(path) else os.path.join(cwd, path)
        expanded = os.path.expanduser(absolute)
        # rm does not follow a symlink supplied as the final argument. Preserve
        # deletion of the link itself; a trailing slash can reach its target.
        if not path.endswith(os.sep) and os.path.islink(expanded):
            resolved = os.path.join(
                os.path.realpath(os.path.dirname(expanded)),
                os.path.basename(os.path.normpath(expanded)),
            )
        else:
            resolved = os.path.realpath(expanded)
    project = os.path.realpath(project_dir)
    if resolved == os.path.realpath(os.sep):
        return "recursive rm targets the filesystem root"
    if resolved == home:
        return f"recursive rm targets the home root: {home}"
    if resolved == project:
        return f"recursive rm targets the project root: {project}"
    return None


def decision_reason(
    command: str, cwd: str, project_dir: str, *, depth: int = 0,
) -> str | None:
    """Return a catastrophic literal-target reason, otherwise no decision."""
    if not command or RM_HINT_RE.search(command) is None:
        return None
    if depth > 3:
        return None
    tokens = tokenize(command)
    if tokens is None:
        return None

    for segment in split_subcommands(tokens):
        nested = _nested_shell_command(segment)
        if nested is not None and RM_HINT_RE.search(nested):
            reason = decision_reason(nested, cwd, project_dir, depth=depth + 1)
            if reason:
                return reason

        index = _direct_rm_index(segment)
        if index is not None and _recursive_rm_at(segment, index):
            paths = _paths_after_rm(segment, index)
            for path in paths:
                reason = _target_reason(path, cwd, project_dir)
                if reason:
                    return reason

    # Unresolved, indirect, external, and narrow targets are deliberately left
    # to the selected native permission mode.
    return None
