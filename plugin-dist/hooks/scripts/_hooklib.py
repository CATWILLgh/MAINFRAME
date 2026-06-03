"""Shared scaffolding for MAINFRAME hub hook scripts.

Stdlib only; importable and unit-tested. Hooks run as bare `python3` scripts
invoked by path; the whole plugin-dist is one symlink, so a sibling import
resolves (precedent: comment-discipline-reminder.py importing comment_extract).

SPOF note: a broken edit here would disable every hook that imports it. Hooks
therefore guard the import (`try: import _hooklib ... except: sys.exit(0)`), and
a SessionStart smoke-check announces a failed import LOUDLY once — so the
degradation is a backstopped silent no-op, not an unsignalled hole.

Boundary: HUB_HOOK_FILES is the COMMON self-exclusion set. comment-discipline
keeps its own smaller self-set locally — do NOT merge it into this one.
"""

import json
import os
import subprocess
import sys

# Source-code extensions the hooks scan. Prose/config (.md/.json/.yaml/.txt) is
# skipped on purpose: it legitimately mentions markers (incl. the hub's own docs).
CODE_EXTENSIONS = frozenset({
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
    ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
})

# Basenames of the hub's own detector hooks + this lib + tests. They contain
# marker/debug patterns as detector logic or test fixtures; flagging them would
# be a self-reference false-positive. Keep in sync with the file names.
HUB_HOOK_FILES = frozenset({
    "scan-suppression-markers.py", "stop-gate-suppression-markers.py",
    "python-security-scan.py", "python-security-stop-gate.py",
    "nodejs-security-scan.py", "nodejs-security-stop-gate.py",
    "nodejs-deps-audit.py", "python-deps-audit.py",
    "bash-pattern-reminder.py", "comment-discipline-reminder.py",
    "frontend-fsd-gate.py", "frontend-dead-code.py",
    "_hooklib.py", "_markers.py", "test_hooklib.py", "test_markers.py",
})


def ext(path):
    """Lowercased file extension including the dot, or '' if the name has none."""
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def load_payload():
    """Parse the hook JSON payload from stdin; return {} on any error."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def emit_note(event, text):
    """Emit a non-blocking additionalContext note (PostToolUse / SessionStart)."""
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}
    }))


def emit_block(reason):
    """Emit a Stop-hook hard block with a reason."""
    print(json.dumps({"decision": "block", "reason": reason}))


def stop_guard_cwd(payload):
    """For Stop hooks: return the cwd to inspect, or None to no-op.

    None is returned when this stop was already blocked once this turn
    (`stop_hook_active`), which prevents an infinite block loop.
    """
    if payload.get("stop_hook_active"):
        return None
    return payload.get("cwd") or "."


def read_git_head(file_path):
    """Content of `git HEAD:<path>` if the file is tracked, else None.

    Lets a Write-overwrite diff against HEAD so only *added* markers are flagged.
    Any failure (not a repo, untracked, timeout, git absent) returns None.
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
            return None
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=2,
        ).decode()
    except Exception:
        return None


def added_lines_by_file(cwd, self_files=HUB_HOOK_FILES):
    """List of (ext, added_line_body) for `+` lines in `git diff HEAD` across
    source-code files, skipping the hub's own detector files.

    Extracted here ONLY because the `+++`/`b/` header parsing is fiddly and the
    hub mandates testing it — not for reuse (one caller today). Returns [] if git
    is unavailable or the cwd is not a work tree.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "HEAD", "--unified=0", "--no-color"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="replace")
    except Exception:
        return []
    current_ext = None
    rows = []
    for line in out.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            e = ext(path)
            ok = e in CODE_EXTENSIONS and os.path.basename(path) not in self_files
            current_ext = e if ok else None
            continue
        if current_ext is None:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        rows.append((current_ext, line[1:]))
    return rows


def run(main_fn):
    """Fail-safe entrypoint: run main_fn(), swallow any error, always exit 0.

    A hook must never break or noise-up a session because of itself.
    """
    try:
        main_fn()
    except Exception:
        pass
    sys.exit(0)
