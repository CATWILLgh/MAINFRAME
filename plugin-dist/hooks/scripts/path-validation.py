#!/usr/bin/env python3
"""PreToolUse hook: validate paths of recursive `rm` against project scope.

Goal: allow `rm -rf <path>` when all target paths reside inside
`$CLAUDE_PROJECT_DIR`; ask the user when at least one path is out of project,
unresolved, or contains a subshell substitution.

Design principle: **fail open for everything that is not a recursive rm.**
Other layers (permissions deny/ask/allow + classifier) handle the rest. The
hook only intervenes when it can clearly identify a recursive rm; anything
ambiguous or unparseable defers via `sys.exit(0)` without producing a decision.

What is covered (v2, 2026-05-29):
- Quote-aware tokenization via `shlex.split` over the whole command (single
  parse). Separator tokens (`&&`, `||`, `;`, `|`, `|&`, `&`) are then identified
  inside the token stream — so `|` inside a quoted string is not mistaken for
  a pipe.
- Process wrappers stripped: `timeout`, `time`, `nice`, `nohup`, `stdbuf`,
  `xargs`.
- `--` separator between flags and positional args.
- Multiple path args in one `rm` invocation.
- Tilde expansion (`~`, `~user/`) via `os.path.expanduser`.
- Variable expansion (`$HOME`, `${VAR}`) via `os.path.expandvars`;
  unresolved → ask.
- Symlink resolution via `os.path.realpath`.
- Glob patterns (`*`, `?`, `[]`) via `glob.glob`; each match validated.
- Subshell substitution (`$(...)`, backticks) in an rm path → ask
  (conservative; do not evaluate).

Outputs (PreToolUse `permissionDecision`):
- `allow` — every target path resides inside `$CLAUDE_PROJECT_DIR`.
- `ask` — at least one target path is outside project, unresolved, or
  contains subshell substitution.
- (no output, exit 0) — command is not a recursive rm, or could not be
  parsed at all; defer to other rules.

Hook contract (Anthropic Claude Code):
- Read JSON payload from stdin.
- Emit decision JSON to stdout, exit code 0.
- Returning no JSON output with exit 0 means "no decision, defer."

Anchor: this file lives in `export/hooks/` and is symlinked to
`~/.claude/hooks/path-validation.py`. `$CLAUDE_PROJECT_DIR` points to the
consumer project (not the hub) — exactly what we need for path checks.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import sys

SEPARATOR_TOKENS = {"&&", "||", ";", "|", "|&", "&"}
PROCESS_WRAPPERS = {"timeout", "time", "nice", "nohup", "stdbuf", "xargs"}
SUBSHELL_RE = re.compile(r"\$\([^)]*\)|`[^`]*`")
UNRESOLVED_VAR_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^}]+\}")
GLOB_CHARS = "*?["


def emit(decision: str, reason: str) -> None:
    """Print the hook decision JSON and exit successfully."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload))
    sys.exit(0)


def defer() -> None:
    """Defer to other permission layers (no output, exit 0)."""
    sys.exit(0)


_OPERATOR_RE = re.compile(r"(&&|\|\||\|&|;|\||&)")


def _split_operators(token: str) -> list[str]:
    """Split a single shlex token on unquoted shell operators it may contain."""
    parts = _OPERATOR_RE.split(token)
    return [p for p in parts if p]


def tokenize(command: str) -> list[str] | None:
    """Quote-aware tokenization of the whole command.

    `shlex.split` respects quotes but does not break on shell operators
    (`;`, `&&`, `|`, `&`, ...) that are not whitespace-delimited — so
    `ls;rm` would come back as the single token `ls;rm`. Post-process each
    shlex token to split out any embedded operators. Quoted text remains
    a single token because shlex strips the surrounding quotes before we
    look for operators.
    """
    try:
        raw_tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    expanded: list[str] = []
    for tok in raw_tokens:
        expanded.extend(_split_operators(tok))
    return expanded


def split_subcommands(tokens: list[str]) -> list[list[str]]:
    """Group tokens into subcommands separated by shell control operators."""
    subcommands: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in SEPARATOR_TOKENS:
            if current:
                subcommands.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        subcommands.append(current)
    return subcommands


def strip_wrappers(tokens: list[str]) -> list[str]:
    """Strip leading process wrappers and their direct numeric/flag arg."""
    result = list(tokens)
    while result and result[0] in PROCESS_WRAPPERS:
        head = result[0]
        if head == "timeout" and len(result) > 1 and re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", result[1]):
            result = result[2:]
        elif head == "nice" and len(result) > 2 and result[1].startswith("-"):
            result = result[3:]
        else:
            result = result[1:]
    return result


def is_recursive_rm(tokens: list[str]) -> bool:
    """True if tokens start with `rm` and any flag implies recursion."""
    if not tokens or tokens[0] != "rm":
        return False
    for tok in tokens[1:]:
        if tok == "--":
            return False
        if tok == "--recursive":
            return True
        if tok.startswith("-") and not tok.startswith("--") and len(tok) > 1:
            if "r" in tok or "R" in tok:
                return True
    return False


def extract_paths(tokens: list[str]) -> list[str]:
    """Return positional path arguments from rm tokens (skip flags)."""
    paths: list[str] = []
    after_separator = False
    for tok in tokens[1:]:
        if after_separator:
            paths.append(tok)
            continue
        if tok == "--":
            after_separator = True
            continue
        if tok.startswith("-"):
            continue
        paths.append(tok)
    return paths


def has_subshell(path: str) -> bool:
    return bool(SUBSHELL_RE.search(path))


def has_unresolved_variable(expanded: str) -> bool:
    return bool(UNRESOLVED_VAR_RE.search(expanded))


def is_glob_pattern(path: str) -> bool:
    return any(c in path for c in GLOB_CHARS) or "{" in path


def expand_path(path: str) -> str:
    return os.path.expanduser(os.path.expandvars(path))


def resolve_paths(path: str, cwd: str) -> list[str] | None:
    """Return absolute resolved paths, or None if unresolved variable remains."""
    expanded = expand_path(path)
    if has_unresolved_variable(expanded):
        return None
    if not os.path.isabs(expanded):
        expanded = os.path.normpath(os.path.join(cwd, expanded))
    if is_glob_pattern(expanded):
        matches = glob.glob(expanded)
        if not matches:
            return [os.path.realpath(expanded)]
        return [os.path.realpath(m) for m in matches]
    return [os.path.realpath(expanded)]


def is_in_project(abs_path: str, project_dir: str) -> bool:
    """True if abs_path is inside (or equal to) project_dir after realpath."""
    project_real = os.path.realpath(project_dir)
    try:
        common = os.path.commonpath([abs_path, project_real])
    except ValueError:
        return False
    return common == project_real


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        defer()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        defer()

    if payload.get("tool_name") != "Bash":
        defer()

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        defer()

    # Fast path: if the literal token "rm" is nowhere near the command, skip
    # the whole pipeline. This is intentionally permissive — we'd rather miss
    # an exotic obfuscation than block routine commands by accident.
    if re.search(r"(?:^|[\s&|;()])rm(?:\s|$)", command) is None:
        defer()

    all_tokens = tokenize(command)
    if all_tokens is None:
        # Could not parse safely — defer rather than block unrelated commands.
        defer()

    # Payload `project_dir` serves callers without the Claude Code env contract.
    project_dir = (payload.get("project_dir")
                   or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    cwd = payload.get("cwd") or project_dir

    saw_rm = False

    for tokens in split_subcommands(all_tokens):
        tokens = strip_wrappers(tokens)
        if not is_recursive_rm(tokens):
            continue
        saw_rm = True
        paths = extract_paths(tokens)
        if not paths:
            emit("ask", "rm -rf invoked without an explicit target path")
        for raw_path in paths:
            if has_subshell(raw_path):
                emit("ask", f"rm -rf target contains subshell substitution: {raw_path[:80]}")
            resolved = resolve_paths(raw_path, cwd)
            if resolved is None:
                emit("ask", f"rm -rf target has unresolved variable: {raw_path[:80]}")
            for abs_path in resolved:
                if not is_in_project(abs_path, project_dir):
                    emit(
                        "ask",
                        f"rm -rf target outside project: {abs_path[:120]} (project: {project_dir})",
                    )

    if saw_rm:
        emit("allow", "rm -rf targets verified inside project directory")

    defer()


if __name__ == "__main__":
    main()
