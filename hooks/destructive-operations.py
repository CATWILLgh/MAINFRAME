#!/usr/bin/env python3
"""Recognize a small set of catastrophic shell and Git operations.

This is the canonical, product-agnostic detector for the
``destructive-operations`` hook. Call :func:`decision_reason` immediately
before a shell action. A returned string is a hard-block reason. ``None``
means that this detector makes no decision and the receiving product's native
permission layer remains authoritative.

The detector protects the filesystem root, the current user's home root, the
active project root, and a narrow set of Git operations that bypass Git's own
safeguards or can destroy recovery data. It does not inspect conversation
history, infer authorization, create approval state, or replace the native
permission layer. If a blocked Git operation is genuinely intended, run it
manually outside the agent or deliberately change the installed policy.

This is not a complete shell parser or sandbox. If a compound command may
change its working directory before a relative recursive deletion, the
detector blocks that compound form and asks for a separate action with an
explicit working directory instead of trying to emulate a shell.

Adapter requirements:

* pass the exact command, tool working directory, active project root, and
  current user's home root when the native payload exposes them;
* translate a returned reason into the product's documented pre-action hard
  denial for both primary agents and subagents;
* emit nothing when the result is ``None``;
* treat missing required payload fields or detector failure as non-blocking
  unavailable protection, never as evidence that the command is dangerous;
* add no telemetry, persistent state, approval inference, or product-specific
  schema to this file.
"""

from __future__ import annotations

import os
import re
import shlex


OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SHELL_COMMANDS = {"sh", "bash", "zsh", "dash", "ksh"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec", "nohup", "time"}
RUNTIME_WRAPPERS = {"sudo", "doas", "env", "timeout", "nice", "stdbuf"}
DIRECTORY_BUILTINS = {"cd", "pushd", "popd"}
RM_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?rm(?=\s|$)")
GIT_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?git(?=\s|$)")
GIT_GLOBAL_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}
PUSH_OPTIONS_WITH_VALUE = {
    "-o",
    "--exec",
    "--push-option",
    "--receive-pack",
    "--repo",
}
MANUAL_GIT_SUFFIX = (
    "Run it manually outside the agent if this operation is genuinely intended."
)


def tokenize(command: str) -> list[str] | None:
    """Tokenize shell operators while preserving operators inside quotes."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def split_subcommands(tokens: list[str]) -> list[list[str]]:
    """Return command segments in source order without executing them."""
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


def _direct_command_index(tokens: list[str]) -> int | None:
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    while index < len(tokens) and _basename(tokens[index]) in SIMPLE_WRAPPERS:
        index += 1
    return index if index < len(tokens) else None


def _recursive_rm_at(tokens: list[str], index: int) -> bool:
    if index >= len(tokens) or _basename(tokens[index]) != "rm":
        return False
    for token in tokens[index + 1 :]:
        if token == "--":
            return False
        if token == "--recursive":
            return True
        if token.startswith("-") and not token.startswith("--"):
            if "r" in token[1:] or "R" in token[1:]:
                return True
    return False


def _wrapped_command_index(tokens: list[str], index: int) -> int | None:
    """Locate a command behind the small supported runtime-wrapper set."""
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
        cursor += 1
    return cursor if cursor < len(tokens) else None


def _executable_index(tokens: list[str]) -> int | None:
    """Locate the executable behind the small supported wrapper set."""
    index = _direct_command_index(tokens)
    while index is not None and index < len(tokens):
        executable = _basename(tokens[index])
        if executable in SIMPLE_WRAPPERS:
            index += 1
            continue
        if executable in RUNTIME_WRAPPERS:
            index = _wrapped_command_index(tokens, index)
            continue
        return index
    return None


def _direct_rm_index(tokens: list[str]) -> int | None:
    index = _executable_index(tokens)
    if index is not None and _basename(tokens[index]) == "rm":
        return index
    return None


def _git_invocation(tokens: list[str]) -> tuple[str, list[str]] | None:
    index = _executable_index(tokens)
    if index is None or _basename(tokens[index]) != "git":
        return None

    cursor = index + 1
    while cursor < len(tokens):
        token = tokens[cursor]
        if token in {"--help", "--version", "-h"}:
            return None
        if token == "--":
            cursor += 1
            break
        option = token.split("=", 1)[0]
        if option in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            cursor += 1 if "=" in token else 2
            continue
        if token.startswith("-"):
            cursor += 1
            continue
        break

    if cursor >= len(tokens):
        return None
    return _basename(tokens[cursor]), tokens[cursor + 1 :]


def _has_long_option(arguments: list[str], option: str) -> bool:
    return any(token == option or token.startswith(option + "=") for token in arguments)


def _has_short_option(arguments: list[str], option: str) -> bool:
    return any(
        token.startswith("-") and not token.startswith("--") and option in token[1:]
        for token in arguments
    )


def _positionals(
    arguments: list[str],
    *,
    options_with_value: set[str] | None = None,
) -> list[str]:
    values = options_with_value or set()
    result: list[str] = []
    after_separator = False
    skip_value = False
    for token in arguments:
        if skip_value:
            skip_value = False
            continue
        if after_separator:
            result.append(token)
            continue
        if token == "--":
            after_separator = True
            continue
        if token.startswith("-"):
            option = token.split("=", 1)[0]
            if option in values and "=" not in token:
                skip_value = True
            continue
        result.append(token)
    return result


def _dry_run(arguments: list[str]) -> bool:
    return _has_long_option(arguments, "--dry-run") or _has_short_option(arguments, "n")


def _help_only(arguments: list[str]) -> bool:
    return any(token in {"-h", "--help"} for token in arguments)


def _push_bypasses_safety(arguments: list[str]) -> bool:
    if _dry_run(arguments):
        return False
    if any(
        _has_long_option(arguments, option)
        for option in (
            "--force",
            "--force-if-includes",
            "--force-with-lease",
            "--mirror",
        )
    ):
        return True
    if _has_short_option(arguments, "f"):
        return True
    return any(
        token.startswith("+")
        for token in _positionals(
            arguments,
            options_with_value=PUSH_OPTIONS_WITH_VALUE,
        )
    )


def _symbolic_ref_mutates(arguments: list[str]) -> bool:
    if _has_long_option(arguments, "--delete") or _has_short_option(arguments, "d"):
        return True
    return len(_positionals(arguments, options_with_value={"-m"})) > 1


def _replace_mutates(arguments: list[str]) -> bool:
    if not arguments:
        return False
    if any(
        _has_long_option(arguments, option)
        for option in (
            "--convert-graft-file",
            "--delete",
            "--edit",
            "--force",
            "--graft",
        )
    ):
        return True
    if any(_has_short_option(arguments, option) for option in ("d", "e", "f", "g")):
        return True
    return len(_positionals(arguments, options_with_value={"--format"})) > 1


def _git_destruction_reason(tokens: list[str]) -> str | None:
    invocation = _git_invocation(tokens)
    if invocation is None:
        return None
    subcommand, arguments = invocation
    if _help_only(arguments):
        return None

    if (
        subcommand in {"am", "commit", "merge", "push", "rebase"}
        and _has_long_option(arguments, "--no-verify")
    ) or (subcommand == "commit" and _has_short_option(arguments, "n")):
        return "Git verification bypass is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand in {"commit-tree", "send-pack"}:
        return (
            f"Low-level Git command {subcommand!r} bypasses ordinary safeguards. "
            + MANUAL_GIT_SUFFIX
        )

    if subcommand == "push" and _push_bypasses_safety(arguments):
        return "Force or mirror push is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "reset" and _has_long_option(arguments, "--hard"):
        return "Git hard reset can discard uncommitted work. " + MANUAL_GIT_SUFFIX

    if subcommand == "clean" and not _dry_run(arguments):
        return "Git clean can permanently delete untracked work. " + MANUAL_GIT_SUFFIX

    if subcommand == "reflog":
        operation = _positionals(arguments)[:1]
        if (
            operation
            and operation[0] in {"delete", "expire"}
            and not _dry_run(arguments)
        ):
            return "Deleting Git reflog recovery data is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "prune" and not _dry_run(arguments):
        return "Pruning unreachable Git objects is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "gc" and any(
        token in {"--prune=all", "--prune=now"} for token in arguments
    ):
        return (
            "Immediate pruning of Git recovery objects is blocked. " + MANUAL_GIT_SUFFIX
        )

    if subcommand == "filter-branch":
        return "Mass Git history rewriting is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "filter-repo" and not (
        _dry_run(arguments)
        or _has_long_option(arguments, "--analyze")
        or _has_long_option(arguments, "--version")
    ):
        return "Mass Git history rewriting is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "branch":
        forced_delete = _has_short_option(arguments, "D") or (
            (
                _has_long_option(arguments, "--delete")
                or _has_short_option(arguments, "d")
            )
            and (
                _has_long_option(arguments, "--force")
                or _has_short_option(arguments, "f")
            )
        )
        if forced_delete:
            return "Forced Git branch deletion is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "worktree":
        operation = _positionals(arguments)[:1]
        if operation == ["remove"] and (
            _has_long_option(arguments, "--force") or _has_short_option(arguments, "f")
        ):
            return "Forced Git worktree removal is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "stash" and _positionals(arguments)[:1] == ["clear"]:
        return "Clearing every Git stash is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "update-ref":
        return "Direct Git ref mutation is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "symbolic-ref" and _symbolic_ref_mutates(arguments):
        return "Direct Git symbolic-ref mutation is blocked. " + MANUAL_GIT_SUFFIX

    if subcommand == "replace" and _replace_mutates(arguments):
        return "Direct Git replacement-ref mutation is blocked. " + MANUAL_GIT_SUFFIX

    return None


def _changes_directory(tokens: list[str]) -> bool:
    index = _direct_command_index(tokens)
    return index is not None and _basename(tokens[index]) in DIRECTORY_BUILTINS


def _paths_after_rm(tokens: list[str], index: int) -> list[str]:
    paths: list[str] = []
    after_separator = False
    for token in tokens[index + 1 :]:
        if after_separator:
            paths.append(token)
        elif token == "--":
            after_separator = True
        elif not token.startswith("-"):
            paths.append(token)
    return paths


def _nested_shell_command(tokens: list[str]) -> str | None:
    index = _executable_index(tokens)
    if index is None or _basename(tokens[index]) not in SHELL_COMMANDS | {"eval"}:
        return None
    if _basename(tokens[index]) == "eval":
        return " ".join(tokens[index + 1 :]) if len(tokens) > index + 1 else None
    for cursor, token in enumerate(tokens[index + 1 :], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            return tokens[cursor + 1] if cursor + 1 < len(tokens) else None
    return None


def _expand_home(path: str, home_root: str) -> str:
    if path == "~":
        return home_root
    if path.startswith("~/"):
        return os.path.join(home_root, path[2:])
    return os.path.expanduser(path)


def _depends_on_current_directory(path: str, home_root: str) -> bool:
    if path in {"$HOME", "${HOME}"}:
        return False
    if "$" in path or "`" in path or any(char in path for char in "?*[]{}"):
        return not os.path.isabs(path)
    return not os.path.isabs(_expand_home(path, home_root))


def _target_reason(
    path: str,
    cwd: str,
    project_root: str,
    home_root: str,
) -> str | None:
    if path in {"$HOME", "${HOME}"}:
        resolved = home_root
    elif "$" in path or "`" in path or any(char in path for char in "?*[]{}"):
        return None
    else:
        expanded = _expand_home(path, home_root)
        absolute = expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)
        # ``rm`` removes a symlink supplied as the final argument. A trailing
        # slash can traverse the link and therefore must resolve its target.
        if not path.endswith(os.sep) and os.path.islink(absolute):
            resolved = os.path.join(
                os.path.realpath(os.path.dirname(absolute)),
                os.path.basename(os.path.normpath(absolute)),
            )
        else:
            resolved = os.path.realpath(absolute)

    filesystem = os.path.realpath(os.sep)
    project = os.path.realpath(project_root)
    if resolved == filesystem:
        return "recursive rm targets the filesystem root"
    if resolved == home_root:
        return f"recursive rm targets the home root: {home_root}"
    if resolved == project:
        return f"recursive rm targets the active project root: {project}"
    return None


def decision_reason(
    command: str,
    cwd: str,
    project_root: str,
    home_root: str | None = None,
    *,
    depth: int = 0,
) -> str | None:
    """Return a hard-block reason, otherwise leave the decision to the host."""
    if not isinstance(command, str) or not command:
        return None
    if RM_HINT_RE.search(command) is None and GIT_HINT_RE.search(command) is None:
        return None
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("destructive-operations requires the shell working directory")
    if not isinstance(project_root, str) or not project_root:
        raise ValueError("destructive-operations requires the active project root")
    if depth > 3:
        return None

    home = os.path.realpath(home_root or os.path.expanduser("~"))
    tokens = tokenize(command)
    if tokens is None:
        return None

    directory_may_have_changed = False
    for segment in split_subcommands(tokens):
        nested = _nested_shell_command(segment)
        if nested is not None and (
            RM_HINT_RE.search(nested) or GIT_HINT_RE.search(nested)
        ):
            if directory_may_have_changed and RM_HINT_RE.search(nested):
                return (
                    "recursive rm follows a working-directory change that "
                    "cannot be verified safely; run the deletion separately "
                    "with the intended working directory"
                )
            reason = decision_reason(
                nested,
                cwd,
                project_root,
                home,
                depth=depth + 1,
            )
            if reason:
                return reason

        git_reason = _git_destruction_reason(segment)
        if git_reason:
            return git_reason

        index = _direct_rm_index(segment)
        if index is not None and _recursive_rm_at(segment, index):
            paths = _paths_after_rm(segment, index)
            for path in paths:
                if directory_may_have_changed and _depends_on_current_directory(
                    path, home
                ):
                    return (
                        "recursive rm follows a working-directory change that "
                        "cannot be verified safely; run the deletion separately "
                        "with the intended working directory"
                    )
                reason = _target_reason(path, cwd, project_root, home)
                if reason:
                    return reason

        if _changes_directory(segment):
            directory_may_have_changed = True

    return None
