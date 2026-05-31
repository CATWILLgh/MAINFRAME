#!/usr/bin/env python3
"""Stop hook: hard gate against unresolved suppression markers.

Fires when Claude is about to stop a turn. If the session's *working-tree diff
vs `git HEAD`* contains newly-added suppression / placeholder markers in
source-code files, block the stop with a reason — forcing Claude to resolve
them (or obtain explicit user permission) before declaring the turn done.

Design (v1):
- Block via `{"decision": "block", "reason": ...}` on stdout, exit 0. Source:
  Anthropic Claude Code hooks docs, "Stop decision control".
- Self-loop guard: if `stop_hook_active` is true on input, exit 0 silently.
  This prevents the gate from blocking forever once Claude is mid-cleanup.
- Diff-aware: read added (`+`) lines from `git diff HEAD` in the session cwd.
  Working-tree state captures markers introduced this session that are still
  not resolved. Lines that came from prior commits (legacy markers) do not
  appear as `+`, so they are not flagged.
- Whitelist: only flag added lines in files whose extension is a known source
  extension. Prose/config (.md/.json/.yaml) legitimately mentions these
  markers (including the hub's own docs); never block on those.
- Fail-safe: any error -> exit 0 without output. The gate must never break
  or noise-up a session because of itself.
- Stdlib only. No venv, no third-party deps.

NOTE: marker definitions are duplicated from `scan-suppression-markers.py`;
keep in sync. A shared module is the cleaner refactor — deferred so the
two hooks can be installed and tested independently first.
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

# Basenames of the hub's own marker-detection hooks. They legitimately contain
# marker regexes/strings as detector logic; flagging them would be a self-
# reference false-positive (and would self-block this hook on its first commit).
_SELF_FILES = {
    "scan-suppression-markers.py", "stop-gate-suppression-markers.py",
    "python-security-scan.py", "python-security-stop-gate.py",
    "nodejs-security-scan.py", "nodejs-security-stop-gate.py",
    "nodejs-deps-audit.py", "python-deps-audit.py",
    "bash-pattern-reminder.py",
    "frontend-fsd-gate.py", "frontend-dead-code.py",
}

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


def _added_markers_in_diff(cwd):
    """Run `git diff HEAD` in `cwd`; return labels of markers present in added
    (`+`) lines of source-code files. Return None if git is unavailable or the
    cwd is not a git work tree — caller treats None as "no-op, let Claude stop".
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "HEAD", "--unified=0", "--no-color"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="replace")
    except Exception:
        return None

    current_file_ok = False
    found = set()
    for line in out.splitlines():
        if line.startswith("+++ "):
            # `+++ b/path/to/file` (or `+++ /dev/null` for deletes)
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            current_file_ok = (
                _ext(path) in CODE_EXTENSIONS
                and os.path.basename(path) not in _SELF_FILES
            )
            continue
        if not current_file_ok:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        for label, rx in MARKERS:
            if rx.search(body):
                found.add(label)
    return sorted(found)


def main():
    payload = json.load(sys.stdin)

    # Self-loop guard: if we already blocked this stop once, let it through.
    if payload.get("stop_hook_active"):
        return

    cwd = payload.get("cwd") or "."
    labels = _added_markers_in_diff(cwd)
    if not labels:
        return  # nothing found, or git unavailable -> let Claude stop

    reason = (
        "Suppression/placeholder markers are present in the working-tree diff "
        f"vs HEAD: {', '.join(labels)}. Per the global engineering rule these "
        "are not allowed in work declared complete. Resolve them in the "
        "affected source files (or obtain explicit user permission to keep "
        "them) before stopping the turn."
    )
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-safe: never break or noise-up a session because of this hook.
        pass
    sys.exit(0)
