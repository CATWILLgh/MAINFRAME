#!/usr/bin/env python3
"""Inspect an agent-initiated Git commit for newly introduced secrets.

This canonical detector is product agnostic. Call :func:`check_command`
immediately before a shell action. A positive high-confidence match produces a
hard-block reason. A technical inability to inspect the commit produces a
non-blocking advisory. Everything else is silent.

The detector reads only Git metadata and content relevant to the prospective
commit. It never reads a credential store, changes the index or worktree,
creates state, records telemetry, or emits a matched value. Adapter code owns
native payload parsing and output encoding.
"""

from __future__ import annotations

from collections import Counter
import dataclasses
import os
from pathlib import Path
import re
import shlex
import subprocess


GIT_TIMEOUT_SECONDS = 5
MAX_COMMAND_CHARS = 100_000
MAX_BLOB_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_CHANGED_PATHS = 512
MAX_FINDINGS = 5

SECRET_PATTERNS = (
    ("github_pat", re.compile(rb"ghp_[0-9a-zA-Z]{36}")),
    ("github_oauth", re.compile(rb"(?:gho|ghu|ghs|ghr)_[0-9a-zA-Z]{36}")),
    (
        "openai_key",
        re.compile(
            rb"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,74}"
            rb"T3BlbkFJ[A-Za-z0-9_-]{20,74}"
        ),
    ),
    (
        "aws_access_key",
        re.compile(
            rb"(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|A3T[A-Z0-9])"
            rb"[A-Z0-9]{16}"
        ),
    ),
    ("slack_token", re.compile(rb"xox[baprs]-[0-9]{8,13}-[0-9]{8,13}-[A-Za-z0-9]{24}")),
    ("stripe_key", re.compile(rb"(?:sk|pk|rk)_(?:test|live)_[0-9a-zA-Z]{10,99}")),
    ("private_key_block", re.compile(rb"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY-----")),
)

PLACEHOLDER_KEYWORDS = (b"example", b"placeholder")
OPERATORS = {"&&", "||", ";", "|", "|&", "&", "(", ")"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
SIMPLE_WRAPPERS = {"command", "builtin", "exec"}
DYNAMIC_TEXT_RE = re.compile(r"\$|`|<\(|>\(")
DYNAMIC_PATH_RE = re.compile(r"\$|`|[?*\[{}]|<\(|>\(")
GIT_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[^\s;&|()]*/)?git(?=\s|$)")
COMMIT_HINT_RE = re.compile(r"(?<![A-Za-z0-9_])commit(?=\s|$)")


@dataclasses.dataclass(frozen=True)
class CheckResult:
    """Product-neutral hook result."""

    block_reason: str | None = None
    advisory: str | None = None


@dataclasses.dataclass(frozen=True)
class CommitInvocation:
    cwd: str
    mode: str
    pathspecs: tuple[str, ...] = ()
    inline_metadata: tuple[tuple[str, str], ...] = ()
    file_metadata: tuple[tuple[str, str], ...] = ()


@dataclasses.dataclass(frozen=True)
class ChangedPath:
    status: str
    old_path: str | None
    new_path: str | None


@dataclasses.dataclass(frozen=True)
class SecretOccurrence:
    kind: str
    value: bytes = dataclasses.field(repr=False)
    line: int | None = None


class InspectionUnavailable(Exception):
    """The prospective commit could not be inspected without guessing."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _is_placeholder(value: bytes) -> bool:
    lowered = value.lower()
    return (
        any(keyword in lowered for keyword in PLACEHOLDER_KEYWORDS)
        or re.search(rb"x{6,}", lowered) is not None
        or re.search(rb"(.)\1{7,}", value) is not None
    )


def _occurrences(data: bytes) -> list[SecretOccurrence]:
    found: list[SecretOccurrence] = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(data):
            value = match.group(0)
            if not _is_placeholder(value):
                found.append(
                    SecretOccurrence(
                        kind=kind,
                        value=value,
                        line=data.count(b"\n", 0, match.start()) + 1,
                    )
                )
    return sorted(found, key=lambda item: item.line or 0)


def _introduced(old: bytes, new: bytes) -> list[SecretOccurrence]:
    old_counts = Counter((item.kind, item.value) for item in _occurrences(old))
    introduced: list[SecretOccurrence] = []
    for item in _occurrences(new):
        key = (item.kind, item.value)
        if old_counts[key]:
            old_counts[key] -= 1
        else:
            introduced.append(item)
    return introduced


def _line_heredocs(line: str) -> list[tuple[str, bool]]:
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError as exc:
        raise InspectionUnavailable("shell_parse") from exc
    found: list[tuple[str, bool]] = []
    index = 0
    while index < len(tokens):
        if tokens[index] != "<<":
            index += 1
            continue
        index += 1
        if index >= len(tokens):
            raise InspectionUnavailable("shell_parse")
        delimiter = tokens[index]
        strip_tabs = delimiter.startswith("-")
        if strip_tabs:
            delimiter = delimiter[1:]
        if not delimiter or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", delimiter) is None:
            raise InspectionUnavailable("shell_parse")
        found.append((delimiter, strip_tabs))
        index += 1
    return found


def _strip_heredoc_bodies(command: str) -> str:
    output: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in command.splitlines(keepends=True):
        if pending:
            delimiter, strip_tabs = pending[0]
            candidate = line.rstrip("\r\n")
            if strip_tabs:
                candidate = candidate.lstrip("\t")
            if candidate == delimiter:
                pending.pop(0)
                if not pending:
                    output.append(";\n")
            continue
        output.append(line)
        pending.extend(_line_heredocs(line))
    if pending:
        raise InspectionUnavailable("shell_parse")
    return "".join(output)


def _tokenize(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(
            _strip_heredoc_bodies(command),
            posix=True,
            punctuation_chars=";&|()",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError as exc:
        raise InspectionUnavailable("shell_parse") from exc


def _segments(tokens: list[str]) -> tuple[list[list[str]], list[str]]:
    segments: list[list[str]] = []
    operators: list[str] = []
    current: list[str] = []
    for token in tokens:
        if token in OPERATORS:
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
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) is not None


def _command_index(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and _is_assignment(tokens[index]):
        if tokens[index].split("=", 1)[0].startswith("GIT_"):
            raise InspectionUnavailable("git_environment_override")
        index += 1
    while index < len(tokens) and os.path.basename(tokens[index]) in SIMPLE_WRAPPERS:
        index += 1
    return index


def _literal_directory(base: str, value: str) -> str:
    if not value or value == "-" or DYNAMIC_PATH_RE.search(value):
        raise InspectionUnavailable("dynamic_directory")
    expanded = os.path.expanduser(value)
    return os.path.realpath(expanded if os.path.isabs(expanded) else os.path.join(base, expanded))


def _nested_command(tokens: list[str]) -> str | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) not in SHELLS:
        return None
    if os.path.basename(tokens[index]) == "eval":
        return " ".join(tokens[index + 1 :]) if index + 1 < len(tokens) else None
    for offset, token in enumerate(tokens[index + 1 :], index + 1):
        if token == "-c" or (token.startswith("-") and "c" in token[1:]):
            if offset + 1 >= len(tokens):
                raise InspectionUnavailable("nested_shell_missing_command")
            return tokens[offset + 1]
    return None


def _parse_commit_args(args: list[str], cwd: str) -> CommitInvocation:
    stages_all = False
    include = False
    only = False
    dry_run = False
    pathspecs: list[str] = []
    inline_metadata: list[tuple[str, str]] = []
    file_metadata: list[tuple[str, str]] = []
    value_options = {
        "-m",
        "--message",
        "-F",
        "--file",
        "--author",
        "--date",
        "-C",
        "--reuse-message",
        "-c",
        "--reedit-message",
        "--fixup",
        "--squash",
        "--cleanup",
        "--trailer",
        "-t",
        "--template",
    }
    unsupported = {"-p", "--patch", "--interactive", "--pathspec-from-file", "--pathspec-file-nul"}
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
            raise InspectionUnavailable("interactive_or_external_pathspec")
        if token in {"-a", "--all"} or (
            token.startswith("-") and not token.startswith("--") and "a" in token[1:]
        ):
            stages_all = True
        if token in {"-i", "--include"}:
            include = True
        if token in {"-o", "--only"}:
            only = True
        if token == "--dry-run":
            dry_run = True
        if option in value_options:
            if "=" in token:
                value = token.split("=", 1)[1]
            else:
                index += 1
                if index >= len(args):
                    raise InspectionUnavailable("commit_option_missing_value")
                value = args[index]
            if option in {"-m", "--message", "--author", "--trailer"}:
                label = "message" if option in {"-m", "--message"} else option.lstrip("-")
                inline_metadata.append((label, value))
            elif option in {"-F", "--file"}:
                if value == "-":
                    raise InspectionUnavailable("stdin_commit_metadata")
                file_metadata.append(("commit-message-file", value))
            index += 1
            continue
        if token.startswith("-"):
            if not token.startswith("--") and "m" in token[1:]:
                suffix = token[token.index("m") + 1 :]
                if suffix:
                    inline_metadata.append(("message", suffix))
                else:
                    index += 1
                    if index >= len(args):
                        raise InspectionUnavailable("commit_option_missing_value")
                    inline_metadata.append(("message", args[index]))
            index += 1
            continue
        pathspecs.append(token)
        index += 1

    if any(DYNAMIC_PATH_RE.search(path) for path in pathspecs):
        raise InspectionUnavailable("dynamic_pathspec")
    if only and not pathspecs:
        raise InspectionUnavailable("only_without_pathspec")
    if dry_run:
        mode = "dry-run"
    elif include and pathspecs:
        mode = "include"
    elif pathspecs:
        mode = "only"
    elif stages_all:
        mode = "all"
    else:
        mode = "index"
    return CommitInvocation(
        cwd=cwd,
        mode=mode,
        pathspecs=tuple(pathspecs),
        inline_metadata=tuple(inline_metadata),
        file_metadata=tuple(file_metadata),
    )


def _parse_git_segment(tokens: list[str], cwd: str) -> CommitInvocation | None:
    index = _command_index(tokens)
    if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
        return None
    index += 1
    effective_cwd = cwd
    while index < len(tokens):
        token = tokens[index]
        if token == "-C":
            index += 1
            if index >= len(tokens):
                raise InspectionUnavailable("git_c_missing_value")
            effective_cwd = _literal_directory(effective_cwd, tokens[index])
            index += 1
            continue
        if token.startswith(("--git-dir", "--work-tree", "--config-env")) or token == "--bare":
            raise InspectionUnavailable("custom_git_scope")
        if token == "-c" or token.startswith("-c"):
            raise InspectionUnavailable("git_config_override")
        if token in {"--no-pager", "--paginate", "-P", "-p"}:
            index += 1
            continue
        if token == "commit":
            return _parse_commit_args(tokens[index + 1 :], effective_cwd)
        if token.startswith("-"):
            raise InspectionUnavailable("unsupported_git_global_option")
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
        if option in {"-i", "--ignore-environment", "-C", "--chdir", "-S", "--split-string"}:
            raise InspectionUnavailable("env_scope_override")
        if option in {"-u", "--unset"}:
            if "=" in token:
                value = token.split("=", 1)[1]
            else:
                index += 1
                if index >= len(tokens):
                    raise InspectionUnavailable("env_option_missing_value")
                value = tokens[index]
            if value.startswith("GIT_"):
                raise InspectionUnavailable("git_environment_override")
            index += 1
            continue
        raise InspectionUnavailable("unsupported_env_option")
    while index < len(tokens) and _is_assignment(tokens[index]):
        if tokens[index].split("=", 1)[0].startswith("GIT_"):
            raise InspectionUnavailable("git_environment_override")
        index += 1
    return tokens[index:] if index < len(tokens) else []


def parse_commit_invocations(command: str, cwd: str, *, depth: int = 0) -> list[CommitInvocation]:
    if depth > 3:
        raise InspectionUnavailable("nested_shell_depth")
    tokens = _tokenize(command)
    segments, operators = _segments(tokens)
    if any(operator in {"(", ")"} for operator in operators):
        if any("commit" in segment for segment in segments):
            raise InspectionUnavailable("shell_group")
    if any(
        os.path.basename(segment[_command_index(segment)]) == "cd"
        for segment in segments
        if _command_index(segment) < len(segment)
    ) and any(operator not in {"&&", ";"} for operator in operators):
        raise InspectionUnavailable("conditional_directory_change")

    invocations: list[CommitInvocation] = []
    effective_cwd = os.path.realpath(cwd)
    for segment in segments:
        index = _command_index(segment)
        if index >= len(segment):
            continue
        command_name = os.path.basename(segment[index])
        if command_name == "cd":
            if len(segment) != index + 2:
                raise InspectionUnavailable("dynamic_directory")
            effective_cwd = _literal_directory(effective_cwd, segment[index + 1])
            continue
        nested = _nested_command(segment)
        if nested is not None:
            invocations.extend(parse_commit_invocations(nested, effective_cwd, depth=depth + 1))
            continue
        candidate = _unwrap_env(segment)
        parsed = _parse_git_segment(candidate if candidate is not None else segment, effective_cwd)
        if parsed is not None:
            invocations.append(parsed)
            continue
        if "git" in [os.path.basename(token) for token in segment] and "commit" in segment:
            if command_name not in {"echo", "printf", "rg", "grep"}:
                raise InspectionUnavailable("indirect_git_commit")
    return invocations


def _git(root: str, args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
        return result.stdout
    except FileNotFoundError as exc:
        raise InspectionUnavailable("git_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise InspectionUnavailable("git_timeout") from exc
    except subprocess.CalledProcessError as exc:
        raise InspectionUnavailable("git_inspection_failed") from exc


def _repo_root(cwd: str) -> str | None:
    try:
        root = _git(cwd, ["rev-parse", "--show-toplevel"]).decode(errors="replace").strip()
        return root or None
    except InspectionUnavailable as exc:
        if exc.code == "git_inspection_failed":
            return None
        raise


def _base_tree(root: str) -> str:
    try:
        return _git(root, ["rev-parse", "--verify", "HEAD^{tree}"]).decode().strip()
    except InspectionUnavailable as exc:
        if exc.code != "git_inspection_failed":
            raise
        return _git(root, ["hash-object", "-t", "tree", "--stdin"], input_bytes=b"").decode().strip()


def _parse_name_status(raw: bytes) -> list[ChangedPath]:
    fields = raw.split(b"\0")
    if fields and not fields[-1]:
        fields.pop()
    changes: list[ChangedPath] = []
    index = 0
    while index < len(fields):
        status = fields[index].decode("ascii", errors="replace")
        index += 1
        if not status:
            raise InspectionUnavailable("git_diff_format")
        if status[0] in {"R", "C"}:
            if index + 1 >= len(fields):
                raise InspectionUnavailable("git_diff_format")
            old_path = os.fsdecode(fields[index])
            new_path = os.fsdecode(fields[index + 1])
            index += 2
        else:
            if index >= len(fields):
                raise InspectionUnavailable("git_diff_format")
            path = os.fsdecode(fields[index])
            index += 1
            old_path = None if status[0] == "A" else path
            new_path = None if status[0] == "D" else path
        changes.append(ChangedPath(status=status[0], old_path=old_path, new_path=new_path))
    return changes


def _changes(root: str, base: str, *, cached: bool, pathspecs: tuple[str, ...] = ()) -> list[ChangedPath]:
    args = ["diff", "--name-status", "-z", "--find-renames"]
    if cached:
        args.append("--cached")
    args.append(base)
    if pathspecs:
        args.extend(["--", *pathspecs])
    return _parse_name_status(_git(root, args))


def _blob(root: str, spec: str, *, missing_ok: bool = False) -> bytes:
    try:
        data = _git(root, ["cat-file", "blob", spec])
    except InspectionUnavailable as exc:
        if missing_ok and exc.code == "git_inspection_failed":
            return b""
        raise
    if len(data) > MAX_BLOB_BYTES:
        raise InspectionUnavailable("blob_too_large")
    return data


def _working_tree_bytes(root: str, path: str) -> bytes:
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise InspectionUnavailable("invalid_git_path")
    target = os.path.join(os.fsencode(root), os.fsencode(path))
    try:
        if os.path.islink(target):
            data = os.readlink(target)
            return data if isinstance(data, bytes) else os.fsencode(data)
        if os.path.isdir(target) or not os.path.exists(target):
            return b""
        size = os.path.getsize(target)
        if size > MAX_BLOB_BYTES:
            raise InspectionUnavailable("blob_too_large")
        with open(target, "rb") as handle:
            data = handle.read(MAX_BLOB_BYTES + 1)
        if len(data) > MAX_BLOB_BYTES:
            raise InspectionUnavailable("blob_too_large")
        return data
    except InspectionUnavailable:
        raise
    except OSError as exc:
        raise InspectionUnavailable("worktree_read_failed") from exc


def _has_content_filter(root: str, path: str) -> bool:
    raw = _git(root, ["check-attr", "-z", "filter", "working-tree-encoding", "--", path])
    fields = raw.split(b"\0")
    values = fields[2::3]
    return any(value not in {b"", b"unspecified", b"unset"} for value in values)


def _display_path(path: str) -> str:
    redacted = os.fsencode(path)
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(b"<redacted>", redacted)
    safe = "".join(
        character if character.isprintable() else "?"
        for character in os.fsdecode(redacted)
    )
    return safe[:160] + ("..." if len(safe) > 160 else "")


def _scan_change(
    root: str,
    base: str,
    change: ChangedPath,
    *,
    source: str,
) -> list[tuple[str, str, int | None]]:
    if change.new_path is None:
        return []
    old = b""
    if change.old_path is not None:
        old = _blob(root, f"{base}:{change.old_path}", missing_ok=True)
    if source == "index":
        new = _blob(root, f":{change.new_path}")
    elif source == "worktree":
        if _has_content_filter(root, change.new_path):
            raise InspectionUnavailable("filtered_worktree_content")
        new = _working_tree_bytes(root, change.new_path)
    else:
        raise InspectionUnavailable("unknown_content_source")
    return [
        (item.kind, _display_path(change.new_path), item.line)
        for item in _introduced(old, new)
    ]


def _scan_metadata(invocation: CommitInvocation) -> list[tuple[str, str, int | None]]:
    findings: list[tuple[str, str, int | None]] = []
    for label, value in invocation.inline_metadata:
        if DYNAMIC_TEXT_RE.search(value):
            raise InspectionUnavailable("dynamic_commit_metadata")
        findings.extend((item.kind, label, item.line) for item in _introduced(b"", os.fsencode(value)))
    for label, value in invocation.file_metadata:
        if DYNAMIC_PATH_RE.search(value):
            raise InspectionUnavailable("dynamic_commit_metadata_file")
        path = value if os.path.isabs(value) else os.path.join(invocation.cwd, value)
        try:
            size = os.path.getsize(path)
            if size > MAX_BLOB_BYTES:
                raise InspectionUnavailable("metadata_file_too_large")
            with open(path, "rb") as handle:
                data = handle.read(MAX_BLOB_BYTES + 1)
        except InspectionUnavailable:
            raise
        except OSError as exc:
            raise InspectionUnavailable("metadata_file_read_failed") from exc
        findings.extend((item.kind, label, item.line) for item in _introduced(b"", data))
    return findings


def _scan_invocation(invocation: CommitInvocation) -> list[tuple[str, str, int | None]]:
    if invocation.mode == "dry-run":
        return []
    root = _repo_root(invocation.cwd)
    if root is None:
        return []
    base = _base_tree(root)
    findings = _scan_metadata(invocation)
    planned: dict[str, tuple[ChangedPath, str]] = {}
    if invocation.mode == "index":
        for change in _changes(root, base, cached=True):
            if change.new_path is not None:
                planned[change.new_path] = (change, "index")
    elif invocation.mode in {"all", "only"}:
        pathspecs = invocation.pathspecs if invocation.mode == "only" else ()
        for change in _changes(root, base, cached=False, pathspecs=pathspecs):
            if change.new_path is not None:
                planned[change.new_path] = (change, "worktree")
    elif invocation.mode == "include":
        for change in _changes(root, base, cached=True):
            if change.new_path is not None:
                planned[change.new_path] = (change, "index")
        for change in _changes(root, base, cached=False, pathspecs=invocation.pathspecs):
            if change.new_path is not None:
                planned[change.new_path] = (change, "worktree")
    else:
        raise InspectionUnavailable("unknown_commit_mode")

    if len(planned) > MAX_CHANGED_PATHS:
        raise InspectionUnavailable("too_many_changed_paths")
    total = 0
    for change, source in planned.values():
        path = change.new_path
        if path is not None:
            if source == "worktree":
                target = os.path.join(root, path)
                if os.path.isfile(target) and not os.path.islink(target):
                    total += os.path.getsize(target)
            else:
                size_text = _git(root, ["cat-file", "-s", f":{path}"]).decode().strip()
                total += int(size_text)
        if total > MAX_TOTAL_BYTES:
            raise InspectionUnavailable("commit_too_large")
        findings.extend(_scan_change(root, base, change, source=source))
    return findings


def _block_reason(findings: list[tuple[str, str, int | None]]) -> str:
    unique = list(dict.fromkeys(findings))[:MAX_FINDINGS]
    listed = "; ".join(
        f"{kind} in {location}{f':{line}' if line is not None else ''}"
        for kind, location, line in unique
    )
    return (
        "Commit blocked: high-confidence secret material would be newly recorded: "
        f"{listed}. Remove it or replace it with an explicit placeholder. The matched "
        "value is intentionally not shown."
    )


def _advisory(code: str) -> str:
    return (
        "MAINFRAME could not inspect the prospective commit for secrets "
        f"({code}); the commit was not blocked by this check. Use a simpler explicit "
        "commit or verify its exact content before continuing."
    )


def check_command(command: str, cwd: str) -> CheckResult:
    """Return a block, an unavailable-check advisory, or a silent result."""
    if not isinstance(command, str) or not isinstance(cwd, str) or not command or not cwd:
        return CheckResult(advisory=_advisory("missing_hook_input"))
    if len(command) > MAX_COMMAND_CHARS:
        return CheckResult(advisory=_advisory("command_too_large"))
    if GIT_HINT_RE.search(command) is None or COMMIT_HINT_RE.search(command) is None:
        return CheckResult()
    try:
        invocations = parse_commit_invocations(command, cwd)
        findings: list[tuple[str, str, int | None]] = []
        for invocation in invocations:
            findings.extend(_scan_invocation(invocation))
    except Exception as exc:
        code = exc.code if isinstance(exc, InspectionUnavailable) else "detector_failure"
        return CheckResult(advisory=_advisory(code))
    if findings:
        return CheckResult(block_reason=_block_reason(findings))
    return CheckResult()
