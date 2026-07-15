"""Shared scaffolding for MAINFRAME hub hook scripts.

Stdlib only; importable and unit-tested. Hooks run as bare `python3` scripts
invoked by path; the deployed scripts dir is one flat directory, so a sibling
import resolves (precedent: comment-discipline-reminder.py importing
comment_extract). Source of truth: `core/gates/detectors/` in the hub repo,
rendered byte-identically here by `tools/render_core.py` — edit the core copy,
never the render output.

SPOF note: a broken edit here would disable every hook that imports it. Hooks
therefore guard the import (`try: import _hooklib ... except: sys.exit(0)`), and
a SessionStart smoke-check announces a failed import LOUDLY once — so the
degradation is a backstopped silent no-op, not an unsignalled hole.

Boundary: HUB_HOOK_FILES is the COMMON self-exclusion set. comment-discipline
keeps its own smaller self-set locally — do NOT merge it into this one.
"""

import datetime
import hashlib
import tempfile
import json
import os
import re
import sqlite3
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
    "stop-gate-comment-discipline.py", "comment_extract.py",
    "frontend-fsd-gate.py", "frontend-dead-code.py",
    "_hooklib.py", "_markers.py", "test_hooklib.py", "test_markers.py",
    "telemetry.py", "test_telemetry.py",
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


def emit_permission(decision, reason):
    """Emit a PreToolUse permission decision (allow / deny / ask).

    The Stop-hook twin is emit_block; this is the PreToolUse shape. On `deny`
    the harness-feedback nudge is appended on dev installs (same non-waiver
    channel as emit_block) so a false positive has a reporting path.
    """
    if decision == "deny" and feedback_skill_installed():
        reason += FEEDBACK_NUDGE
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


# `git [-c k=v | -C path | --opts] commit ...` — the commit subcommand. `-c`/`-C`
# take a value token, so match them before the generic flag alternative. Single
# source for every hook that needs to recognise a commit (the reminder + the
# secret gate) — keep here, not duplicated per script.
_COMMIT_RE = re.compile(r"\bgit\b(?:\s+-[cC]\s+\S+|\s+--?\S+)*\s+commit\b")


def is_git_commit(command):
    """True if the shell command invokes `git commit`."""
    return bool(command and _COMMIT_RE.search(command))


# Appended to stop-gate blocks on dev installs: the hub's false-positive
# signal channel. Non-waiver phrasing is deliberate — the nudge must never
# read as an alternative to fixing the finding.
FEEDBACK_NUDGE = (
    " If a flagged finding is a false positive of this gate, file harness "
    "feedback via the `harness-feedback` skill after resolving — feedback "
    "does not waive the fix."
)


def feedback_skill_installed():
    """True when the dev-only `harness-feedback` skill is installed (env
    `MAINFRAME_FEEDBACK_NUDGE` = 1/0 overrides — tests and explicit opt-out)."""
    override = os.environ.get("MAINFRAME_FEEDBACK_NUDGE")
    if override is not None:
        return override == "1"
    skill_dir = (os.environ.get("MAINFRAME_FEEDBACK_SKILL_DIR")
                 or os.path.expanduser("~/.claude/skills/harness-feedback"))
    return os.path.isdir(skill_dir)


def emit_block(reason):
    """Emit a Stop-hook hard block with a reason (+ nudge on dev installs)."""
    if feedback_skill_installed():
        reason += FEEDBACK_NUDGE
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


def changed_files(cwd, exts):
    """Absolute paths of source files added/modified vs HEAD in `cwd`, filtered
    to `exts` and existence-checked. [] if git is unavailable.

    Unlike added_lines_by_file this does NOT exclude the hub's own detector files
    — the security gates legitimately analyze any changed source file. Absolute
    paths so the caller can hand them straight to an external analyzer.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "HEAD", "--name-only", "--diff-filter=AM"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="replace")
    except Exception:
        return []
    exts = set(exts)
    files = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel or ext(rel) not in exts:
            continue
        abs_path = os.path.join(cwd, rel)
        if os.path.exists(abs_path):
            files.append(abs_path)
    return files


_HUNK_NEW_SIDE_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_line_ranges(cwd):
    """(ranges, ok): new-side line numbers changed vs HEAD, per absolute path.

    `ranges[path]` is a set of line numbers, or None for untracked files (every
    line is new). `ok=False` means git gave no answer — callers must then treat
    every finding as delta (the strict branch): ambiguity may never widen the
    inherited (weakened) branch. Deletion-only hunks contribute no lines, so a
    file edited purely by deletion keeps an empty set — `finding_is_delta`
    reads that as ambiguous, again toward strict.
    """
    try:
        diff = subprocess.check_output(
            ["git", "diff", "HEAD", "-U0", "--no-color", "--diff-filter=AM"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=10).decode(errors="replace")
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=10).decode(errors="replace")
    except Exception:
        return {}, False
    ranges, current = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target.startswith("b/"):
                target = target[2:]
            current = (None if target == "/dev/null"
                       else os.path.realpath(os.path.join(cwd, target)))
            if current is not None:
                ranges.setdefault(current, set())
        elif current is not None and line.startswith("@@"):
            m = _HUNK_NEW_SIDE_RE.match(line)
            if not m:
                continue
            start = int(m.group(1))
            count = 1 if m.group(2) is None else int(m.group(2))
            ranges[current].update(range(start, start + count))
    for rel in untracked.splitlines():
        rel = rel.strip()
        if rel:
            ranges[os.path.realpath(os.path.join(cwd, rel))] = None
    return ranges, True


def finding_is_delta(file_path, start_row, end_row, ranges, git_ok):
    """True when a finding overlaps this session's changed lines — or when the
    classification is ambiguous (no git, file absent from ranges, empty entry).
    Security gates weaken only on a PROVEN inherited finding, never by default."""
    if not git_ok:
        return True
    lines = ranges.get(os.path.realpath(file_path), ())
    if lines is None:
        return True
    if not lines:
        return True
    lo = min(start_row or 0, end_row or start_row or 0)
    hi = max(start_row or 0, end_row or start_row or 0)
    return any(n in lines for n in range(lo, hi + 1))


def tickets_mentioning(cwd, file_path, max_bytes=262144):
    """Ticket files under docs/tickets/ whose text contains the repo-relative
    path of `file_path`. Path anchor, never the basename — `auth.py` is a
    substring of `oauth.py`, and utils.py recurs across any repo."""
    tickets_dir = os.path.join(cwd, "docs", "tickets")
    rel = os.path.relpath(os.path.realpath(file_path), os.path.realpath(cwd))
    rel = rel.replace(os.sep, "/")
    if rel.startswith("..") or not os.path.isdir(tickets_dir):
        return []
    hits = []
    for name in sorted(os.listdir(tickets_dir)):
        if not name.endswith(".md") or name == "README.md":
            continue
        path = os.path.join(tickets_dir, name)
        try:
            if os.path.getsize(path) > max_bytes:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                if rel in fh.read():
                    hits.append(name)
        except OSError:
            continue
    return hits


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


_TELEMETRY_BANNED_KEYS = frozenset({
    "tool_input", "prompt", "command", "content", "code", "text",
    "path", "file_path", "cwd", "transcript_path",
})

# Single owner of the task-workflow engagement marker format: the engagement
# gate writes it, the telemetry sink reads it — a duplicated path computation
# would be a silent cross-hook dependency.
TW_ENGAGE_STATE_DIR = os.path.join(tempfile.gettempdir(), "mainframe-tw-engage")


def tw_engagement_path(session_id):
    key = hashlib.sha256(
        (session_id or "nosession").encode("utf-8")).hexdigest()[:16]
    return os.path.join(TW_ENGAGE_STATE_DIR, key)


def tw_engagement_state(session_id):
    """Per-session-segment marker: 'active' / 'reminded' / 'fresh' / ''."""
    try:
        with open(tw_engagement_path(session_id), encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _telemetry_db_path():
    # ~/.claude/mainframe is the hub-OWNED namespace (a --dev symlink into the
    # hub repo). ~/.claude/telemetry is unusable as an opt-in marker: Claude
    # Code itself creates and uses it, so it exists on every machine.
    return (os.environ.get("MAINFRAME_TELEMETRY_DB")
            or os.path.expanduser("~/.claude/mainframe/telemetry/telemetry.db"))


def _telemetry_project_key(cwd):
    # Stable per-project key that disambiguates same-named dirs without storing
    # the full (potentially sensitive) path.
    if not cwd:
        return ""
    base = os.path.basename(os.path.normpath(cwd))
    digest = hashlib.sha256(cwd.encode("utf-8", "replace")).hexdigest()[:6]
    return f"{base}-{digest}"


def log_event(event, payload=None, hook_payload=None):
    """Append one telemetry row, best-effort — any failure is a silent no-op.

    Passive Bucket-1 sink (ADR 0073). Must never stall or break a session:
    short busy_timeout, whole body guarded. `payload` is event-specific metadata
    — banned structural keys are stripped as a secrets second-line-of-defence.
    `hook_payload` is the hook stdin JSON, read only for session_id / agent_type
    / cwd, never dumped wholesale.
    """
    try:
        hp = hook_payload or {}
        safe = {k: v for k, v in (payload or {}).items()
                if k not in _TELEMETRY_BANNED_KEYS}
        row = (
            datetime.datetime.now().isoformat(timespec="seconds"),
            str(hp.get("session_id") or ""),
            str(hp.get("agent_type") or ""),
            _telemetry_project_key(hp.get("cwd") or ""),
            str(event),
            json.dumps(safe, separators=(",", ":")),
            # Which harness emitted the event: Claude Code hooks omit the
            # key; the OpenCode dispatcher sets it. Keeps CC/OC behavior
            # separable in every analysis.
            str(hp.get("source") or "claude-code"),
        )
        db = _telemetry_db_path()
        if os.environ.get("MAINFRAME_TELEMETRY_DB"):
            os.makedirs(os.path.dirname(db), exist_ok=True)
        elif not os.path.isdir(os.path.dirname(db)):
            return  # dir absent = telemetry not opted in (dev-only, install.sh --dev)
        conn = sqlite3.connect(db, timeout=0.05)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=50")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, session_id TEXT, "
                "agent_type TEXT, project TEXT, event TEXT, payload TEXT, "
                "source TEXT DEFAULT 'claude-code')")
            try:
                # Pre-source DBs: constant default backfills existing rows.
                conn.execute("ALTER TABLE events ADD COLUMN source TEXT "
                             "DEFAULT 'claude-code'")
            except sqlite3.OperationalError:
                pass
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts)")
            conn.execute(
                "INSERT INTO events(ts, session_id, agent_type, project, event, "
                "payload, source) VALUES (?,?,?,?,?,?,?)", row)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def run(main_fn):
    """Fail-safe entrypoint: run main_fn(), swallow any error, always exit 0.

    A hook must never break or noise-up a session because of itself.
    """
    try:
        main_fn()
    except Exception:
        pass
    sys.exit(0)
