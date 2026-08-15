#!/usr/bin/env python3
"""Block a Git commit that may introduce a high-confidence secret."""

from __future__ import annotations

import dataclasses
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_permission, load_payload, log_hook_signal, run
except Exception:
    sys.exit(0)


SECRET_PATTERNS = [
    ("github_pat", re.compile(r"ghp_[0-9a-zA-Z]{36}")),
    ("github_oauth", re.compile(r"(?:gho|ghu|ghs|ghr)_[0-9a-zA-Z]{36}")),
    ("openai_key", re.compile(
        r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,74}"
        r"T3BlbkFJ[A-Za-z0-9_-]{20,74}")),
    ("aws_access_key", re.compile(
        r"(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])[A-Z0-9]{16}")),
    ("slack_token", re.compile(
        r"xox[baprs]-[0-9]{8,13}-[0-9]{8,13}-[A-Za-z0-9]{24}")),
    ("stripe_key", re.compile(r"(?:sk|pk|rk)_(?:test|live)_[0-9a-zA-Z]{10,99}")),
    ("private_key_block", re.compile(r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY-----")),
]

_PLACEHOLDER_KEYWORDS = ("example", "placeholder")
_OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
_UNSAFE_PATH_RE = re.compile(r"\$|`|[?*\[{}]|<\(|>\(")
_GIT_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?git(?=\s|$)")
_COMMIT_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])commit(?=\s|$)")


class VerificationError(Exception):
    """The exact commit content cannot be established safely."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class CommitInvocation:
    cwd: str
    mode: str
    pathspecs: tuple[str, ...] = ()


def _is_placeholder(token: str) -> bool:
    low = token.lower()
    return (
        any(keyword in low for keyword in _PLACEHOLDER_KEYWORDS)
        or bool(re.search(r"x{6,}", low))
        or bool(re.search(r"(.)\1{7,}", token))
    )


def _scan_diff_text(text: str) -> list[tuple[str, str]]:
    """Return token kind and basename for secrets on added text lines."""
    findings: list[tuple[str, str]] = []
    current = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            current = None if path == "/dev/null" else os.path.basename(path)
            continue
        if current is None or not line.startswith("+") or line.startswith("+++"):
            continue
        for kind, pattern in SECRET_PATTERNS:
            match = pattern.search(line[1:])
            if match and not _is_placeholder(match.group(0)):
                findings.append((kind, current))
                break
    return findings


def _tokenize(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError as exc:
        raise VerificationError("shell_parse") from exc


def _segments(tokens: list[str]) -> tuple[list[list[str]], list[str]]:
    segments: list[list[str]] = []
    operators: list[str] = []
    current: list[str] = []
    for token in tokens:
        if token in _OPERATORS:
            if current:
                segments.append(current)
                current = []
            operators.append(token)
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments, operators


def _is_assignment(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token))


def _assignment_name(token: str) -> str | None:
    return token.split("=", 1)[0] if _is_assignment(token) else None


def _reject_git_assignment(token: str) -> None:
    name = _assignment_name(token)
    if name is not None and name.startswith("GIT_"):
        raise VerificationError("git_environment_override")


def _command_index(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        index += 1
    while index < len(tokens) and os.path.basename(tokens[index]) in {"command", "builtin"}:
        index += 1
    return index


def _resolve_literal_dir(base: str, value: str) -> str:
    if not value or value == "-" or _UNSAFE_PATH_RE.search(value):
        raise VerificationError("dynamic_directory")
    expanded = os.path.expanduser(value)
    return os.path.realpath(
        expanded if os.path.isabs(expanded) else os.path.join(base, expanded))


def _nested_command(tokens: list[str]) -> str | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) not in _SHELLS:
        return None
    if os.path.basename(tokens[index]) == "eval":
        return " ".join(tokens[index + 1:]) if index + 1 < len(tokens) else None
    for offset, token in enumerate(tokens[index + 1:], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            if offset + 1 >= len(tokens):
                raise VerificationError("nested_shell_missing_command")
            return tokens[offset + 1]
    return None


def _parse_commit_args(args: list[str], cwd: str) -> CommitInvocation:
    stages_all = False
    include = False
    only = False
    pathspecs: list[str] = []
    value_options = {
        "-m", "--message", "-F", "--file", "--author", "--date",
        "-C", "--reuse-message", "-c", "--reedit-message", "--fixup",
        "--squash", "--cleanup", "--trailer", "-t", "--template",
    }
    unsupported = {
        "-p", "--patch", "--interactive", "--pathspec-from-file",
        "--pathspec-file-nul",
    }
    index = 0
    after_separator = False
    while index < len(args):
        token = args[index]
        if after_separator:
            pathspecs.append(token)
            index += 1
            continue
        if token == "--":
            after_separator = True
            index += 1
            continue
        option = token.split("=", 1)[0]
        if option in unsupported:
            raise VerificationError("interactive_or_external_pathspec")
        if token in {"-a", "--all"} or (
            token.startswith("-") and not token.startswith("--") and "a" in token[1:]
        ):
            stages_all = True
        if token in {"-i", "--include"}:
            include = True
        if token in {"-o", "--only"}:
            only = True
        if option in value_options:
            if "=" not in token:
                index += 1
                if index >= len(args):
                    raise VerificationError("commit_option_missing_value")
            index += 1
            continue
        if token.startswith("-"):
            # Short -m can be combined (-am message) or carry an inline value
            # (-amessage). Consume the next token only when m is final.
            if not token.startswith("--") and "m" in token[1:]:
                suffix = token[token.index("m") + 1:]
                if not suffix:
                    index += 1
                    if index >= len(args):
                        raise VerificationError("commit_option_missing_value")
            index += 1
            continue
        pathspecs.append(token)
        index += 1

    if any(_UNSAFE_PATH_RE.search(path) for path in pathspecs):
        raise VerificationError("dynamic_pathspec")
    if only and not pathspecs:
        raise VerificationError("only_without_pathspec")
    mode = "include" if include and pathspecs else (
        "only" if pathspecs else ("all" if stages_all else "index"))
    return CommitInvocation(cwd=cwd, mode=mode, pathspecs=tuple(pathspecs))


def _parse_git_segment(tokens: list[str], cwd: str) -> CommitInvocation | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
        return None
    if "commit" not in tokens[index + 1:]:
        return None
    index += 1
    effective_cwd = cwd
    while index < len(tokens):
        token = tokens[index]
        if token == "-C":
            index += 1
            if index >= len(tokens):
                raise VerificationError("git_c_missing_value")
            effective_cwd = _resolve_literal_dir(effective_cwd, tokens[index])
            index += 1
            continue
        if (
            token.startswith("--git-dir")
            or token.startswith("--work-tree")
            or token == "--bare"
        ):
            raise VerificationError("custom_git_directory")
        if (
            token == "-c"
            or token.startswith("-c")
            or token.startswith("--config-env")
        ):
            raise VerificationError("git_config_override")
        if token in {"--no-pager", "--paginate", "-P", "-p"}:
            index += 1
            continue
        if token == "commit":
            return _parse_commit_args(tokens[index + 1:], effective_cwd)
        if token.startswith("-"):
            raise VerificationError("unsupported_git_global_option")
        return None
    return None


def _unwrap_env(tokens: list[str]) -> list[str] | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "env":
        return None
    index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
        token = tokens[index]
        option = token.split("=", 1)[0]
        if token == "--":
            index += 1
            break
        if option in {"-i", "--ignore-environment"}:
            raise VerificationError("env_ignore_environment")
        if option in {"-C", "--chdir", "-S", "--split-string"}:
            raise VerificationError("env_scope_override")
        if option in {"-u", "--unset"}:
            if "=" in token:
                value = token.split("=", 1)[1]
            else:
                index += 1
                if index >= len(tokens):
                    raise VerificationError("env_option_missing_value")
                value = tokens[index]
            if value.startswith("GIT_"):
                raise VerificationError("git_environment_override")
            index += 1
            continue
        raise VerificationError("unsupported_env_option")
    while index < len(tokens) and _is_assignment(tokens[index]):
        _reject_git_assignment(tokens[index])
        index += 1
    return tokens[index:] if index < len(tokens) else []


def parse_commit_invocations(command: str, cwd: str, *, depth: int = 0) -> list[CommitInvocation]:
    if depth > 3:
        raise VerificationError("nested_shell_depth")
    tokens = _tokenize(command)
    segments, operators = _segments(tokens)
    if any(operator in {"(", ")"} for operator in operators):
        # Parenthesized shell groups can alter directory scope independently.
        if any("commit" in segment for segment in segments):
            raise VerificationError("shell_group")
    if any(os.path.basename(segment[_command_index(segment)]) == "cd"
           for segment in segments if _command_index(segment) < len(segment)):
        if any(operator not in {"&&", ";"} for operator in operators):
            raise VerificationError("conditional_directory_change")

    invocations: list[CommitInvocation] = []
    effective_cwd = os.path.realpath(cwd)
    for segment in segments:
        for token in segment:
            if not _is_assignment(token):
                break
            _reject_git_assignment(token)
        index = _command_index(segment)
        if index >= len(segment):
            continue
        command_name = os.path.basename(segment[index])
        if command_name == "cd":
            if len(segment) != index + 2:
                raise VerificationError("dynamic_directory")
            effective_cwd = _resolve_literal_dir(effective_cwd, segment[index + 1])
            continue
        nested = _nested_command(segment)
        if nested is not None:
            invocations.extend(parse_commit_invocations(
                nested, effective_cwd, depth=depth + 1))
            continue
        candidate = _unwrap_env(segment)
        parsed = _parse_git_segment(
            candidate if candidate is not None else segment, effective_cwd)
        if parsed is not None:
            invocations.append(parsed)
            continue
        if "git" in [os.path.basename(token) for token in segment] and "commit" in segment:
            command_name = os.path.basename(segment[index])
            if command_name not in {"echo", "printf"}:
                raise VerificationError("indirect_git_commit")
    return invocations


def _git(root: str, args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.DEVNULL,
            timeout=5).decode(errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise VerificationError("git_inspection_failed") from exc


def _repo_root(cwd: str) -> str | None:
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        return root or None
    except (OSError, subprocess.SubprocessError):
        return None


def _base_tree(root: str) -> str:
    try:
        return _git(root, ["rev-parse", "--verify", "HEAD^{tree}"]).strip()
    except VerificationError:
        # Works for SHA-1 and SHA-256 repositories without writing an object.
        try:
            result = subprocess.run(
                ["git", "hash-object", "-t", "tree", "--stdin"], cwd=root,
                input=b"", capture_output=True, timeout=2, check=True)
            return result.stdout.decode().strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise VerificationError("empty_tree_failed") from exc


def _diff(root: str, args: list[str]) -> str:
    return _git(root, ["diff", "--unified=0", "--no-color", *args])


def _scan_invocation(invocation: CommitInvocation) -> list[tuple[str, str]] | None:
    root = _repo_root(invocation.cwd)
    if root is None:
        return None  # git commit itself will fail: this is not a gate outage.
    if invocation.mode == "index":
        text = _diff(root, ["--cached"])
    else:
        base = _base_tree(root)
        if invocation.mode == "all":
            text = _diff(root, [base])
        elif invocation.mode == "only":
            text = _diff(root, [base, "--", *invocation.pathspecs])
        elif invocation.mode == "include":
            text = _diff(root, ["--cached"])
            text += _diff(root, [base, "--", *invocation.pathspecs])
        else:
            raise VerificationError("unknown_commit_mode")
    return _scan_diff_text(text)


def _deny_unverified(code: str, payload: dict) -> None:
    reason = (
        "Commit blocked because MAINFRAME could not verify the exact content "
        f"that Git would record ({code}). Use a simpler explicit git commit "
        "command or inspect and commit manually."
    )
    emitted_reason = emit_permission("deny", reason)
    log_hook_signal(
        __file__, "unverified-commit-scope", "blocked", 1, payload,
        context=emitted_reason,
    )


def main() -> None:
    payload = load_payload()
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if _GIT_HINT_RE.search(command) is None or _COMMIT_HINT_RE.search(command) is None:
        return
    cwd = payload.get("cwd") or os.getcwd()
    try:
        invocations = parse_commit_invocations(command, cwd)
        findings: list[tuple[str, str]] = []
        for invocation in invocations:
            result = _scan_invocation(invocation)
            if result is not None:
                findings.extend(result)
    except VerificationError as exc:
        _deny_unverified(exc.code, payload)
        return
    if not invocations or not findings:
        return

    unique = list(dict.fromkeys(findings))
    listed = "; ".join(f"{kind} in {name}" for kind, name in unique[:5])
    reason = (
        "Commit blocked: high-confidence secret material was found in the "
        f"content Git would record: {listed}. Remove it before committing; "
        "the matched value is intentionally not shown. Pass secrets through "
        "an environment variable or the `secret` helper, and use an explicit "
        "placeholder for documentation examples."
    )
    emitted_reason = emit_permission("deny", reason)
    log_hook_signal(
        __file__, "secret-material", "blocked", len(unique), payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
