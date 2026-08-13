#!/usr/bin/env python3
"""Enforce primary-session Git delivery and explicit branch authority."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import log_hook_signal, run
except Exception:
    sys.exit(0)


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
ENV_OPTIONS_WITH_VALUE = {
    "-u", "--unset", "-C", "--chdir", "-S", "--split-string", "--argv0",
}
GIT_OPTIONS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env", "--exec-path",
}
MUTATING_BRANCH_OPTIONS = {
    "-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy",
    "-f", "--force", "--edit-description", "--set-upstream-to", "-u",
    "--unset-upstream", "--create-reflog", "--track", "-t", "--no-track",
    "--recurse-submodules",
}
READ_BRANCH_OPTIONS = {
    "-a", "--all", "-r", "--remotes", "-l", "--list", "-v", "-vv",
    "--verbose", "--show-current", "--contains", "--no-contains", "--merged",
    "--no-merged", "--points-at", "--format", "--sort", "--column",
    "--no-column", "--color", "--no-color", "-i", "--ignore-case",
    "--omit-empty", "--abbrev", "--no-abbrev", "--help", "-h",
}


def _tokenize(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list[str]) -> list[list[str]]:
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


def _is_assignment(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token))


def _command_index(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    if index < len(tokens) and os.path.basename(tokens[index]) == "env":
        index += 1
        while index < len(tokens):
            token = tokens[index]
            option = token.split("=", 1)[0]
            if _is_assignment(token) or token == "--":
                index += 1
                continue
            if option in ENV_OPTIONS_WITH_VALUE:
                index += 1 if "=" in token else 2
                continue
            if token.startswith("-"):
                index += 1
                continue
            break
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


def _git_branch_arguments(tokens: list[str]) -> list[str] | None:
    subcommand = _git_subcommand(tokens)
    if subcommand is None or subcommand[0] != "branch":
        return None
    return subcommand[1]


def _git_subcommand(tokens: list[str]) -> tuple[str, list[str]] | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
        return None
    index += 1
    while index < len(tokens):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if option in GIT_OPTIONS_WITH_VALUE:
            index += 1 if "=" in token else 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(tokens):
        return None
    return tokens[index], tokens[index + 1:]


def _option_name(token: str) -> str:
    return token.split("=", 1)[0]


def _branch_arguments_mutate(arguments: list[str]) -> bool:
    if not arguments:
        return False
    options = {_option_name(token) for token in arguments if token.startswith("-")}
    if options & MUTATING_BRANCH_OPTIONS:
        return True
    if options & READ_BRANCH_OPTIONS:
        return False
    # A positional argument without an explicit listing selector is the branch
    # name in `git branch <name> [<start-point>]` and therefore creates it.
    return any(not token.startswith("-") for token in arguments)


def branch_mutation_reason(command: str, *, depth: int = 0) -> str | None:
    if depth > 3 or "branch" not in command:
        return None
    tokens = _tokenize(command)
    if tokens is None:
        return None
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            reason = branch_mutation_reason(nested, depth=depth + 1)
            if reason:
                return reason
            continue
        arguments = _git_branch_arguments(segment)
        if arguments is not None and _branch_arguments_mutate(arguments):
            return (
                "Creating, deleting, renaming, or retargeting a Git branch "
                "requires explicit authorization from the immediate caller."
            )
    return None


def _subagent_delivery_mutation(command: str, *, depth: int = 0) -> bool:
    if depth > 3 or "git" not in command:
        return False
    tokens = _tokenize(command)
    if tokens is None:
        return False
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            if _subagent_delivery_mutation(nested, depth=depth + 1):
                return True
            continue
        subcommand = _git_subcommand(segment)
        if subcommand is not None and subcommand[0] in {"add", "stage", "commit"}:
            return True
    return False


def authority_decision(command: str, agent_id=None) -> tuple[str | None, str | None]:
    if agent_id and _subagent_delivery_mutation(command):
        return "deny", (
            "Staging and local commits belong to the primary session. "
            "Leave the working-tree changes unstaged and return the result and "
            "verification to your immediate caller."
        )
    reason = branch_mutation_reason(command)
    return ("ask", reason) if reason else (None, None)


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    decision, reason = authority_decision(command, payload.get("agent_id"))
    if not decision:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    log_hook_signal(
        __file__, "git-delivery-authority",
        "asked" if decision == "ask" else "blocked", 1, payload,
        context=reason,
    )


if __name__ == "__main__":
    run(main)
