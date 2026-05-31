#!/usr/bin/env python3
"""PostToolUse hook: surface a soft reminder when a code edit adds new comments.

Goal — not a gate, not a block. Comments aren't suppression markers; the rule
is "default to no comments, comment only the WHY". Detection is purely regex
on diff; the model decides if any added comment is genuine WHY or an
anti-pattern (Position/Phase Marker, Journal/Byline, Redundant Paraphrase,
Noise) per the CLAUDE.md Engineering rule.

Design:
- Non-blocking: PostToolUse cannot block anyway; only emits additionalContext.
- Diff-aware: counts comment-lines added vs removed. Triggers only on net
  increase. Refactor that replaces one comment with another is silent.
- Source-code files only (same CODE_EXTENSIONS as scan-suppression-markers).
  Markdown, prose, config files skipped — comments there are normal content.
- Fail-safe: any error -> exit 0 with no output. Hook must never disrupt.
- Stdlib only: bare python3, no venv.

Detection scope (v1, single-line comment syntaxes):
- C-style "//"  (JS, TS, C, C++, Java, Go, Rust, Swift, Kotlin, Scala, Dart)
- Hash "#"      (Python, Ruby, shell, etc.) — skips shebangs ("#!")
- SQL/Haskell/Lua "--"

Multi-line block comments (slash-star ... star-slash), Python triple-quoted
docstrings, and HTML angle-bracket comments are deferred — they require
state-machine parsing and false-positive rate is higher. The model still
sees the actual diff; this hook is only the reminder layer.
"""

import json
import os
import re
import subprocess
import sys

CODE_EXTENSIONS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
    ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
}

_SELF_FILES = {"comment-discipline-reminder.py"}

COMMENT_LINE_PATTERNS = [
    re.compile(r"^\s*//"),
    re.compile(r"^\s*#(?!!)"),  # skip shebangs ("#!")
    re.compile(r"^\s*--"),
]


def _ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def _count_comment_lines(text):
    if not text:
        return 0
    count = 0
    for line in text.splitlines():
        for rx in COMMENT_LINE_PATTERNS:
            if rx.match(line):
                count += 1
                break
    return count


def _net_added(old_text, new_text):
    return _count_comment_lines(new_text) - _count_comment_lines(old_text)


def _read_git_head(file_path):
    if not file_path:
        return None
    cwd = os.path.dirname(file_path) or "."
    try:
        rel = subprocess.check_output(
            ["git", "ls-files", "--full-name", file_path],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        if not rel:
            return None
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2,
        ).decode()
    except Exception:
        return None


def _collect_added(tool_name, tool_input):
    if tool_name == "Edit":
        return _net_added(
            tool_input.get("old_string", "") or "",
            tool_input.get("new_string", "") or "",
        )
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        old = "".join(e.get("old_string", "") or "" for e in edits)
        new = "".join(e.get("new_string", "") or "" for e in edits)
        return _net_added(old, new)
    if tool_name == "Write":
        content = tool_input.get("content")
        if content is None:
            content = tool_input.get("file_text", "")
        new = content or ""
        old = _read_git_head(tool_input.get("file_path", ""))
        if old is not None:
            return _net_added(old, new)
        return _count_comment_lines(new)
    return 0


def main():
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    file_path = tool_input.get("file_path", "")
    if not file_path or _ext(file_path) not in CODE_EXTENSIONS:
        return
    if os.path.basename(file_path) in _SELF_FILES:
        return

    added = _collect_added(tool_name, tool_input)
    if added <= 0:
        return

    verb = "edit" if tool_name in ("Edit", "MultiEdit") else "write"
    plural = "s" if added > 1 else ""
    note = (
        f"Heads-up: this {verb} added {added} new comment line{plural}. "
        "Per the engineering rule (default to writing no comments — only "
        "comment the WHY that is non-obvious), check each added comment "
        "against the banned forms: Position/Phase Marker (\"// === Phase B "
        "===\", \"// Step 1 of 3\"), Journal/Byline (\"// added 2024-01-15 "
        "for X\"), Redundant Paraphrase (\"// increments i\"), Nonlocal "
        "Information (facts about other modules), Mandated boilerplate on "
        "trivial getters, Noise (decorative lines, \"// end of if\"). If a "
        "comment captures genuine WHY (hidden constraint, subtle invariant, "
        "workaround for a specific bug) — keep it, and keep it short: one "
        "sentence per non-obvious WHY, not a paragraph. Comments are a "
        "supplement to the code, not a parallel codebase. Otherwise remove "
        "before declaring done. This is a reminder, not a block."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": note,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
