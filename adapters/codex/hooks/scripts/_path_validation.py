#!/usr/bin/env python3
"""Require confirmation for risky or unresolved recursive ``rm`` targets.

This global PreToolUse hook is only a destructive-path circuit breaker. A
plain recursive removal whose literal target resolves strictly below the
project root produces no decision, so Codex command rules and normal approval
handling still apply. The hook never returns ``allow``.
"""

from __future__ import annotations

import os
import re
import shlex


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
RULE_SAFE_OPERATORS = {"&&", "||", ";", "|"}
CWD_COMMANDS = {"cd", "pushd", "popd"}
SHELL_COMMANDS = {"sh", "bash", "zsh", "dash", "ksh"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
RUNTIME_WRAPPERS = {"sudo", "doas", "env", "timeout", "nice", "stdbuf"}
NON_EXECUTING_COMMANDS = {"echo", "printf"}
SHELL_META_RE = re.compile(r"\$|`|[?*\[]|[{}]|<\(|>\(")
RULE_UNSAFE_SYNTAX_RE = re.compile(r"[\r\n<>$`?*\[\]{}]")
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


def _recursive_rm_indices(tokens: list[str]) -> list[int]:
    return [
        index for index in range(len(tokens))
        if _recursive_rm_at(tokens, index)
    ]


def _rule_safe_syntax(command: str, tokens: list[str]) -> bool:
    """Whether Codex rules can split this shell text into argv prefixes."""
    if RULE_UNSAFE_SYNTAX_RE.search(command):
        return False
    if any(token in OPERATORS - RULE_SAFE_OPERATORS for token in tokens):
        return False
    return not any(_is_assignment(token) for token in tokens)


def rule_handles_recursive_rm(command: str) -> bool:
    """True when native rules cover every executable recursive rm segment."""
    tokens = tokenize(command)
    if tokens is None or not _rule_safe_syntax(command, tokens):
        return False
    segments = split_subcommands(tokens)
    # The published contract says simple shell chains are split before rule
    # evaluation, but execpolicy checks on the supported local runtimes do not
    # expose that behavior. Only trust the directly testable argv prefix.
    if len(segments) != 1 or any(token in OPERATORS for token in tokens):
        return False
    found = False
    accepted_options = {
        "-r", "-R", "-rf", "-rF", "-fr", "-fR", "-Rf", "-RF",
        "--recursive",
    }
    for segment in segments:
        recursive = _recursive_rm_indices(segment)
        if not recursive:
            continue
        if _basename(segment[0]) in NON_EXECUTING_COMMANDS:
            continue
        found = True
        if recursive != [0]:
            return False
        if segment[0] not in {"rm", "/bin/rm"}:
            return False
        if len(segment) < 2 or segment[1] not in accepted_options:
            return False
    return found


def _target_reason(path: str, cwd: str, project_dir: str) -> str | None:
    if SHELL_META_RE.search(path):
        return f"recursive rm target requires shell expansion: {path[:100]}"
    absolute = path if os.path.isabs(path) else os.path.join(cwd, path)
    expanded = os.path.expanduser(absolute)
    project = os.path.realpath(project_dir)
    # rm does not follow a symlink supplied as the final argument. Preserve
    # that useful narrow deletion while still resolving symlinked parents and
    # a trailing slash, both of which can reach a tree outside the project.
    if not path.endswith(os.sep) and os.path.islink(expanded):
        resolved = os.path.join(
            os.path.realpath(os.path.dirname(expanded)),
            os.path.basename(os.path.normpath(expanded)),
        )
    else:
        resolved = os.path.realpath(expanded)
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
    """Return an unsafe-target reason, or None for a classifiable command."""
    if not command or RM_HINT_RE.search(command) is None:
        return None
    if "<(" in command or ">(" in command:
        return "recursive rm target requires shell expansion"
    if depth > 3:
        return "recursive rm is nested too deeply to validate safely"
    tokens = tokenize(command)
    if tokens is None:
        return "recursive rm command could not be parsed safely"

    executable_recursive_rm = any(
        _recursive_rm_indices(segment)
        and _basename(segment[0]) not in NON_EXECUTING_COMMANDS
        for segment in split_subcommands(tokens)
    )
    if executable_recursive_rm and not _rule_safe_syntax(command, tokens):
        return "recursive rm uses shell syntax that command rules cannot classify"

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

        recursive_indices = _recursive_rm_indices(segment)
        if (
            recursive_indices
            and _basename(segment[0]) not in NON_EXECUTING_COMMANDS
            and index not in recursive_indices
        ):
            return "recursive rm is not a direct classifiable command"

        if segment and _basename(segment[0]) in CWD_COMMANDS:
            cwd_may_have_changed = True

    # A hint that could not be classified as an executable rm (for example an
    # echoed command) is ignored. A classified safe rm deliberately returns no
    # decision rather than allow, preserving Codex's normal permission flow.
    return None
