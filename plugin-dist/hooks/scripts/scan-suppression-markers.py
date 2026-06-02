#!/usr/bin/env python3
"""PostToolUse hook: flag newly-introduced suppression / placeholder markers.

Reads the PostToolUse hook payload from stdin (JSON), looks at the file just
written/edited, and — only for source-code files — checks whether the change
*introduced* any suppression or placeholder markers (TODO/FIXME, skipped tests,
silenced type/lint checks). If so, it emits a non-blocking `additionalContext`
note so the model self-corrects per the global engineering rule.

Design (v1):
- Non-blocking: PostToolUse cannot block anyway; we only surface a note.
- Diff-aware: for Edit/MultiEdit we flag markers added by the change, not
  markers that already existed (avoids noise on legacy markers). For Write we
  diff against the file's `git HEAD` content when the file is tracked, and
  fall back to a full-content scan otherwise (new files / non-git projects).
- Fail-safe: ANY error -> exit 0 with no output. This hook must never break or
  noise-up a session.
- Stdlib only: no venv, no third-party deps. Runs under a bare `python3`.

Deferred (see docs/layers/hooks.md): Stop-time hard gate is shipped
separately (`stop-gate-suppression-markers.py`); configurable marker set is
still pending.
"""

import json
import os
import re
import subprocess
import sys

# Source-code extensions we scan. Everything else (.md, .json, .yaml, .txt, ...)
# is skipped on purpose: prose/config files legitimately mention these markers
# (including the hub's own docs and this rule's definition).
CODE_EXTENSIONS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
    ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
}

# Basenames of the hub's own marker-detection hook scripts. They legitimately
# contain marker regexes/strings as part of their detector logic; flagging them
# would be a self-reference false-positive. Keep in sync with the file names.
_SELF_FILES = {
    "scan-suppression-markers.py", "stop-gate-suppression-markers.py",
    "python-security-scan.py", "python-security-stop-gate.py",
    "nodejs-security-scan.py", "nodejs-security-stop-gate.py",
    "nodejs-deps-audit.py", "python-deps-audit.py",
    "bash-pattern-reminder.py", "comment-discipline-reminder.py",
    "frontend-fsd-gate.py", "frontend-dead-code.py",
}


# (label, compiled regex). Kept intentionally focused; extend as evidence grows.
MARKERS = [
    ("TODO/FIXME/HACK/XXX comment", re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)),
    ("@ts-ignore / @ts-nocheck", re.compile(r"@ts-(?:ignore|nocheck)\b")),
    ("eslint-disable", re.compile(r"eslint-disable\b")),
    ("# type: ignore", re.compile(r"#\s*type:\s*ignore\b")),
    ("# noqa", re.compile(r"#\s*noqa\b")),
    ("pylint: disable", re.compile(r"pylint:\s*disable\b")),
    ("skipped/focused test (.skip/.only/xit/fit)",
     re.compile(r"(?:\.(?:skip|only)\s*\(|\b(?:xit|fit|xdescribe|fdescribe)\s*\()")),
    ("pytest/unittest skip", re.compile(r"@(?:pytest\.mark\.skip|unittest\.skip)")),
]


def _ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def _added_markers(old_text, new_text):
    """Marker labels whose occurrence count increased from old_text to new_text."""
    found = []
    for label, rx in MARKERS:
        if len(rx.findall(new_text)) > len(rx.findall(old_text)):
            found.append(label)
    return found


def _markers_in(text):
    return [label for label, rx in MARKERS if rx.search(text)]


def _read_git_head(file_path):
    """Return file content from `git HEAD:<path>` if the file is tracked, else None.

    Used to make Write-overwrite diff-aware: if the file existed in git, we
    compare new content against HEAD and only flag *added* markers, instead of
    re-flagging legacy markers on every overwrite. Any failure (not a git repo,
    file not tracked, timeout, git absent) returns None and the caller falls
    back to a full-content scan.
    """
    if not file_path:
        return None
    cwd = os.path.dirname(file_path) or "."
    try:
        rel = subprocess.check_output(
            ["git", "ls-files", "--full-name", file_path],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        if not rel:
            return None  # untracked or outside any git work tree
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2,
        ).decode()
    except Exception:
        return None


def _collect(tool_name, tool_input):
    """Return the list of newly-introduced marker labels for this tool call."""
    if tool_name == "Edit":
        return _added_markers(
            tool_input.get("old_string", "") or "",
            tool_input.get("new_string", "") or "",
        )
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        old = "".join(e.get("old_string", "") or "" for e in edits)
        new = "".join(e.get("new_string", "") or "" for e in edits)
        return _added_markers(old, new)
    if tool_name == "Write":
        # Field name is `content` for the Write tool; tolerate `file_text` too.
        content = tool_input.get("content")
        if content is None:
            content = tool_input.get("file_text", "")
        new = content or ""
        old = _read_git_head(tool_input.get("file_path", ""))
        if old is not None:
            return _added_markers(old, new)
        return _markers_in(new)
    return []


def main():
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    file_path = tool_input.get("file_path", "")
    if not file_path or _ext(file_path) not in CODE_EXTENSIONS:
        return  # not a source-code edit -> nothing to do
    if os.path.basename(file_path) in _SELF_FILES:
        return  # the hub's marker-detector hooks contain marker patterns by design

    labels = []
    for label in _collect(tool_name, tool_input):
        if label not in labels:
            labels.append(label)
    if not labels:
        return

    verb = "edit" if tool_name in ("Edit", "MultiEdit") else "write"
    note = (
        f"Heads-up: this {verb} introduced suppression/placeholder marker(s): "
        f"{', '.join(labels)}. Per the global engineering rule, placeholder "
        "markers (TODO/FIXME/HACK/XXX), skipped/focused tests, and silenced "
        "type/lint checks are not allowed in work you declare complete, and "
        "adding them needs explicit user permission — a failing check is a "
        "contract signal to surface, not to silence. Resolve them or get the "
        "user's OK before declaring the task done."
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
        # Fail-safe: never break or noise-up a session because of this hook.
        pass
    sys.exit(0)
