#!/usr/bin/env python3
"""Enforce primary-session Git delivery and explicit repository authority."""

from __future__ import annotations

import os
import re
import shlex


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time", "noglob"}
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
BRANCH_LIST_OPTIONS = {
    "-a", "--all", "-r", "--remotes", "-l", "--list", "--show-current",
    "--contains", "--no-contains", "--merged", "--no-merged", "--points-at",
}
BRANCH_OPTIONS_WITH_VALUE = {
    "--contains", "--no-contains", "--merged", "--no-merged", "--points-at",
    "--format", "--sort",
}
ASK_SUBCOMMANDS = {
    "checkout", "switch", "pull", "merge", "rebase", "reset",
    "cherry-pick", "revert", "restore",
}
COMMIT_OPTIONS_WITH_VALUE = {
    "-m", "--message", "-F", "--file", "-C", "--reuse-message",
    "-c", "--reedit-message", "-t", "--template", "--fixup", "--squash",
    "--cleanup", "--author", "--date", "--trailer", "--pathspec-from-file",
}
PUSH_OPTIONS_WITH_VALUE = {
    "-o", "--push-option", "--repo", "--receive-pack", "--exec",
}
FETCH_OPTIONS_WITH_VALUE = {
    "--server-option", "--upload-pack", "--depth", "--shallow-since",
    "--shallow-exclude", "--deepen", "-j", "--jobs", "--negotiation-tip",
    "--filter", "--submodule-prefix", "--recurse-submodules", "--refmap",
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


def _backtick_commands(command: str) -> list[str]:
    return re.findall(r"(?<!\\)`([^`]*)`", command)


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
    while index < len(tokens):
        wrapper = os.path.basename(tokens[index])
        if wrapper in SIMPLE_WRAPPERS:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
            continue
        if wrapper == "timeout":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                option = _option_name(tokens[index])
                index += 1
                if option in {"-k", "--kill-after", "-s", "--signal"} and "=" not in tokens[index - 1]:
                    index += 1
            if index < len(tokens):
                index += 1
            continue
        if wrapper == "nice":
            index += 1
            if index < len(tokens) and _option_name(tokens[index]) in {"-n", "--adjustment"}:
                index += 1 if "=" in tokens[index] else 2
            elif index < len(tokens) and re.fullmatch(r"-\d+", tokens[index]):
                index += 1
            continue
        if wrapper == "stdbuf":
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                token = tokens[index]
                index += 1
                if token in {"-i", "-o", "-e", "--input", "--output", "--error"}:
                    index += 1
            continue
        if wrapper == "xargs" and index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
            index += 1
            continue
        break
    return index


def _looks_like_unparsed_git(command: str) -> bool:
    return bool(re.search(r"(^|[\s;&|()`])(?:[^\s;&|()`]*/)?git(?:\s|$)", command))


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


def _has_long_option(
    arguments: list[str], option: str, *, options_with_value: set[str] | None = None,
) -> bool:
    values = options_with_value or set()
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            return False
        name = _option_name(token)
        if name == option:
            return True
        if name in values:
            index += 1 if "=" in token else 2
            continue
        index += 1
    return False


def _has_short_option(
    arguments: list[str], option: str, *, options_with_value: set[str] | None = None,
) -> bool:
    value_options = options_with_value or set()
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            return False
        if re.fullmatch(r"-[A-Za-z]+", token):
            cluster = token[1:]
            for offset, flag in enumerate(cluster):
                if flag == option:
                    return True
                if flag in value_options:
                    if offset == len(cluster) - 1:
                        index += 1
                    break
        index += 1
    return False


def _positionals(
    arguments: list[str], *, options_with_value: set[str] | None = None,
) -> list[str]:
    values = options_with_value or set()
    result: list[str] = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            result.extend(arguments[index + 1:])
            break
        option = _option_name(token)
        if option in values:
            index += 1 if "=" in token else 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        result.append(token)
        index += 1
    return result


def _branch_arguments_mutate(arguments: list[str]) -> bool:
    if not arguments:
        return False
    options = {_option_name(token) for token in arguments if token.startswith("-")}
    if options & MUTATING_BRANCH_OPTIONS:
        return True
    if options & BRANCH_LIST_OPTIONS or options & {"--help", "-h"}:
        return False
    # Formatting flags alone still list branches, but they do not turn a later
    # positional branch name into a listing pattern. Only explicit listing
    # selectors do that.
    return bool(_positionals(arguments, options_with_value=BRANCH_OPTIONS_WITH_VALUE))


def branch_mutation_reason(command: str, *, depth: int = 0) -> str | None:
    if depth > 3 or "branch" not in command:
        return None
    for nested in _backtick_commands(command):
        reason = branch_mutation_reason(nested, depth=depth + 1)
        if reason:
            return reason
    tokens = _tokenize(command)
    if tokens is None:
        return (
            "An unparseable Git command that may change a branch requires "
            "explicit authorization from the immediate caller."
            if _looks_like_unparsed_git(command) else None
        )
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            reason = branch_mutation_reason(nested, depth=depth + 1)
            if reason:
                return reason
            continue
        subcommand = _git_subcommand(segment)
        if (
            subcommand is not None
            and subcommand[0] == "branch"
            and _branch_arguments_mutate(subcommand[1])
        ):
            return (
                "Creating, deleting, renaming, or retargeting a Git branch "
                "requires explicit authorization from the immediate caller."
            )
    return None


def _push_bypasses_safety(arguments: list[str]) -> bool:
    if any(
        _has_long_option(
            arguments, option, options_with_value=PUSH_OPTIONS_WITH_VALUE,
        )
        for option in ("--force", "--force-with-lease", "--force-if-includes", "--mirror")
    ):
        return True
    if _has_short_option(arguments, "f", options_with_value={"o"}):
        return True
    return any(
        token.startswith("+")
        for token in _positionals(arguments, options_with_value=PUSH_OPTIONS_WITH_VALUE)
    )


def _fetch_changes_local_refs(arguments: list[str]) -> bool:
    if any(
        _has_long_option(
            arguments, option, options_with_value=FETCH_OPTIONS_WITH_VALUE,
        )
        for option in ("--update-head-ok", "--refmap", "--force")
    ):
        return True
    if _has_short_option(arguments, "f", options_with_value={"j", "o"}):
        return True
    return any(
        token.startswith("+") or ":" in token
        for token in _positionals(arguments, options_with_value=FETCH_OPTIONS_WITH_VALUE)
    )


def _bypasses_verification(subcommand: str, arguments: list[str]) -> bool:
    if subcommand not in {"am", "commit", "merge", "push", "rebase"}:
        return False
    value_options = COMMIT_OPTIONS_WITH_VALUE if subcommand == "commit" else set()
    if _has_long_option(
        arguments, "--no-verify", options_with_value=value_options,
    ):
        return True
    return subcommand == "commit" and _has_short_option(
        arguments, "n", options_with_value={"m", "F", "C", "c", "t"},
    )


def _stash_mutates(arguments: list[str]) -> bool:
    if not arguments:
        return True
    if arguments[0] in {"list", "show"}:
        return False
    return arguments[0] not in {"-h", "--help"}


def _worktree_mutates(arguments: list[str]) -> bool:
    if not arguments or arguments[0] in {"list", "-h", "--help"}:
        return False
    if arguments[0] == "prune" and (
        _has_long_option(arguments[1:], "--dry-run")
        or _has_short_option(arguments[1:], "n")
    ):
        return False
    return True


def repository_mutation_reason(command: str, *, depth: int = 0) -> tuple[str, str] | None:
    if depth > 3 or "git" not in command:
        return None
    for nested in _backtick_commands(command):
        decision = repository_mutation_reason(nested, depth=depth + 1)
        if decision:
            return decision
    tokens = _tokenize(command)
    if tokens is None:
        if _looks_like_unparsed_git(command):
            return "ask", (
                "This Git command could not be classified safely and requires "
                "explicit authorization from the immediate caller."
            )
        return None
    for segment in _segments(tokens):
        nested = _nested_command(segment)
        if nested is not None:
            decision = repository_mutation_reason(nested, depth=depth + 1)
            if decision:
                return decision
            continue
        parsed = _git_subcommand(segment)
        if parsed is None:
            continue
        subcommand, arguments = parsed
        if _bypasses_verification(subcommand, arguments):
            return "deny", "Git verification checks may not be bypassed."
        if subcommand == "push":
            if _push_bypasses_safety(arguments):
                return "deny", "Force-pushing requires a separate policy decision and is blocked."
            return "ask", "Pushing requires explicit authorization from the immediate caller."
        if subcommand == "fetch" and _fetch_changes_local_refs(arguments):
            return "ask", (
                "A fetch that can directly rewrite local refs requires explicit "
                "authorization from the immediate caller."
            )
        if subcommand == "commit":
            if _has_long_option(arguments, "--amend"):
                return "ask", "Amending Git history requires explicit authorization from the immediate caller."
            continue
        if subcommand == "branch" and _branch_arguments_mutate(arguments):
            return "ask", (
                "Creating, deleting, renaming, or retargeting a Git branch "
                "requires explicit authorization from the immediate caller."
            )
        if subcommand == "stash" and _stash_mutates(arguments):
            return "ask", "Changing the Git stash requires explicit authorization from the immediate caller."
        if subcommand == "worktree" and _worktree_mutates(arguments):
            return "ask", "Changing Git worktrees requires explicit authorization from the immediate caller."
        if subcommand == "clean":
            if (
                _has_long_option(arguments, "--force")
                or _has_short_option(arguments, "f", options_with_value={"e"})
                or _has_long_option(
                    arguments, "--interactive", options_with_value={"-e", "--exclude"},
                )
                or _has_short_option(arguments, "i", options_with_value={"e"})
            ):
                return "ask", "Deleting untracked files requires explicit authorization from the immediate caller."
            continue
        if subcommand in ASK_SUBCOMMANDS:
            return "ask", (
                f"Running git {subcommand} requires explicit authorization "
                "from the immediate caller."
            )
    return None


def _subagent_delivery_mutation(command: str, *, depth: int = 0) -> bool:
    if depth > 3 or "git" not in command:
        return False
    if any(
        _subagent_delivery_mutation(nested, depth=depth + 1)
        for nested in _backtick_commands(command)
    ):
        return True
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
        if (
            subcommand is not None
            and subcommand[0] in {"add", "stage", "commit", "rm", "mv"}
            and not (
                subcommand[0] in {"rm", "mv"}
                and (
                    _has_long_option(subcommand[1], "--dry-run")
                    or _has_short_option(subcommand[1], "n")
                )
            )
        ):
            return True
    return False


def authority_decision(command: str, agent_id=None) -> tuple[str | None, str | None]:
    if agent_id and _subagent_delivery_mutation(command):
        return "deny", (
            "Index changes and local commits belong to the primary session. "
            "Leave the working-tree changes unstaged and return the result and "
            "verification to your immediate caller."
        )
    decision = repository_mutation_reason(command)
    return decision if decision else (None, None)
