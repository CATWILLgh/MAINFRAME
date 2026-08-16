"""Shared scaffolding for MAINFRAME hub hook scripts.

Stdlib only; importable and unit-tested. Hooks run as bare `python3` scripts
invoked by path; the whole adapters/claude-code/plugin is one symlink, so a sibling import
resolves (precedent: comment-discipline-reminder.py importing comment_extract).

SPOF note: a broken edit here would disable every hook that imports it. Hooks
therefore guard the import (`try: import _hooklib ... except: sys.exit(0)`), and
a SessionStart smoke-check announces a failed import LOUDLY once — so the
degradation is a backstopped silent no-op, not an unsignalled hole.

Boundary: HUB_HOOK_FILES is the COMMON self-exclusion set. comment-discipline
keeps its own smaller self-set locally — do NOT merge it into this one.
"""

import datetime
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

try:
    from _telemetry_contract import ROW_SCHEMA_VERSION, validate_payload
except Exception:
    ROW_SCHEMA_VERSION = 0
    validate_payload = None

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
    "nodejs-security-scan.py",
    "bash-pattern-reminder.py", "comment-discipline-reminder.py",
    "stop-gate-comment-discipline.py", "comment_extract.py",
    "_comment_findings.py", "_python_findings.py",
    "_length_check.py", "_length_state.py",
    "length-quality-note.py",
    "_hooklib.py", "_markers.py", "_marker_state.py", "_notice_state.py",
    "test_hooklib.py",
    "telemetry.py", "_telemetry_contract.py", "hook-failure-report.py",
    "test_telemetry.py",
    "skill-authority.py",
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
    return reason


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
    return os.path.isdir(os.path.expanduser("~/.claude/skills/harness-feedback"))


def emit_block(reason):
    """Emit a Stop-hook hard block with a reason (+ nudge on dev installs)."""
    if feedback_skill_installed():
        reason += FEEDBACK_NUDGE
    print(json.dumps({"decision": "block", "reason": reason}))
    return reason


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


def tickets_mentioning(cwd, file_path, max_bytes=262144):
    """Open ticket files whose text contains the repo-relative file path.

    Search every lifecycle directory below docs/tickets/open, but never the
    immutable archive. Match the path anchor rather than a basename: auth.py is
    a substring of oauth.py, and utils.py commonly recurs across a repository.
    """
    tickets_dir = os.path.join(cwd, "docs", "tickets", "open")
    rel = os.path.relpath(os.path.realpath(file_path), os.path.realpath(cwd))
    rel = rel.replace(os.sep, "/")
    if rel.startswith("..") or not os.path.isdir(tickets_dir):
        return []
    hits = []
    for root, dirs, names in os.walk(tickets_dir):
        dirs.sort()
        for name in sorted(names):
            if not name.endswith(".md") or name == "README.md":
                continue
            path = os.path.join(root, name)
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


def _telemetry_db_path():
    # ~/.claude/mainframe is the hub-OWNED --dev namespace. Keep the adapter
    # segment explicit so a future Codex adapter can opt in independently.
    return (os.environ.get("MAINFRAME_TELEMETRY_DB")
            or os.path.expanduser(
                "~/.claude/mainframe/claude-code/telemetry/telemetry.db"))


def _telemetry_project_key(cwd):
    # Stable per-project key that disambiguates same-named dirs without storing
    # the full (potentially sensitive) path.
    if not cwd:
        return ""
    base = os.path.basename(os.path.normpath(cwd))
    digest = hashlib.sha256(cwd.encode("utf-8", "replace")).hexdigest()[:6]
    return f"{base}-{digest}"


_TELEMETRY_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, "
    "schema_version INTEGER NOT NULL, session_id TEXT, prompt_id TEXT, "
    "agent_id TEXT, agent_type TEXT, tool_use_id TEXT, project TEXT, "
    "hook_event TEXT, origin TEXT NOT NULL DEFAULT 'unclassified', "
    "event TEXT NOT NULL, payload TEXT NOT NULL)"
)
_TELEMETRY_MIGRATION_COLUMNS = (
    ("schema_version", "INTEGER NOT NULL DEFAULT 1"),
    ("prompt_id", "TEXT"),
    ("agent_id", "TEXT"),
    ("tool_use_id", "TEXT"),
    ("hook_event", "TEXT"),
    ("origin", "TEXT NOT NULL DEFAULT 'unclassified'"),
)
_TELEMETRY_ORIGINS = frozenset({"runtime", "model-lab", "synthetic", "unclassified"})
_HOOK_SIGNAL_OUTCOMES = frozenset({"noted", "asked", "blocked", "resolved"})
_HOOK_SIGNAL_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_HOOK_SIGNAL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_TELEMETRY_RETRY_DELAYS = (0.0, 0.005, 0.015, 0.030)


def initialize_telemetry_db(db=None):
    """Create the dev-only sink once and configure its persistent WAL mode."""
    path = db or _telemetry_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(_TELEMETRY_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        for name, declaration in _TELEMETRY_MIGRATION_COLUMNS:
            if name not in columns:
                conn.execute(f"ALTER TABLE events ADD COLUMN {name} {declaration}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id, id)")
        # Old revisions created a derived SQL view. The canonical reader now
        # owns every aggregation for both machine and web consumers.
        conn.execute("DROP VIEW IF EXISTS hook_effectiveness")
        conn.execute(f"PRAGMA user_version={ROW_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()
    return path


def _telemetry_busy(exc):
    text = str(exc).lower()
    return "locked" in text or "busy" in text


def _telemetry_origin(hook_payload):
    """Classify provenance without storing transcript paths or test details."""
    explicit = os.environ.get("MAINFRAME_TELEMETRY_ORIGIN")
    if explicit in _TELEMETRY_ORIGINS:
        return explicit
    requested = str((hook_payload or {}).get("_telemetry_origin") or "")
    if requested in _TELEMETRY_ORIGINS:
        return requested
    # An explicit DB is the supported test/debug override. Production hook
    # events use the default dev sink and carry Claude's documented common
    # transcript_path field. Anything else stays visible but unclassified.
    if os.environ.get("MAINFRAME_TELEMETRY_DB"):
        return "synthetic"
    if (hook_payload or {}).get("transcript_path"):
        return "runtime"
    return "unclassified"


def log_event(event, payload=None, hook_payload=None):
    """Append one telemetry row and return written/disabled/busy/error.

    The adapter's shell gate prevents telemetry-only Python startup outside
    --dev. Product hooks that are already running also call this function, so
    the directory check deliberately happens before row construction. In dev,
    schema/WAL initialization belongs to installation; only a missing database
    is repaired lazily. Contending writers receive a short bounded retry with
    process-based jitter and never stall or break a session indefinitely.
    """
    try:
        db = _telemetry_db_path()
        directory = os.path.dirname(db)
        if os.environ.get("MAINFRAME_TELEMETRY_DB"):
            os.makedirs(directory, exist_ok=True)
        elif not os.path.isdir(directory):
            return "disabled"
        if not os.path.exists(db):
            initialize_telemetry_db(db)

        if validate_payload is None or ROW_SCHEMA_VERSION <= 0:
            return "error"
        hp = hook_payload or {}
        safe = validate_payload(str(event), payload or {})
        now = datetime.datetime.now(datetime.timezone.utc)
        origin = _telemetry_origin(hp)
        # The documented hook envelope always contains transcript_path. A
        # default-sink call without it is a direct test/helper invocation, not
        # observable Claude runtime behavior, and must not pollute the live DB.
        if origin == "unclassified" and not os.environ.get("MAINFRAME_TELEMETRY_DB"):
            return "disabled"
        row = (
            now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            ROW_SCHEMA_VERSION,
            str(hp.get("session_id") or ""),
            str(hp.get("prompt_id") or ""),
            str(hp.get("agent_id") or ""),
            str(hp.get("agent_type") or ""),
            str(hp.get("tool_use_id") or ""),
            _telemetry_project_key(hp.get("cwd") or ""),
            str(hp.get("hook_event_name") or ""),
            origin,
            str(event),
            json.dumps(safe, separators=(",", ":")),
        )
        migrated = False
        for attempt, delay in enumerate(_TELEMETRY_RETRY_DELAYS):
            if delay:
                jitter = ((os.getpid() + attempt) % 5) / 1000
                time.sleep(delay + jitter)
            conn = None
            try:
                conn = sqlite3.connect(db, timeout=0.05)
                conn.execute("PRAGMA busy_timeout=50")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute(
                    "INSERT INTO events(ts, schema_version, session_id, prompt_id, "
                    "agent_id, agent_type, tool_use_id, project, hook_event, origin, "
                    "event, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
                conn.commit()
                return "written"
            except sqlite3.OperationalError as exc:
                if not migrated and "column" in str(exc).lower():
                    if conn is not None:
                        conn.close()
                        conn = None
                    initialize_telemetry_db(db)
                    migrated = True
                    continue
                if not _telemetry_busy(exc):
                    return "error"
            finally:
                if conn is not None:
                    conn.close()
        return "busy"
    except sqlite3.OperationalError:
        return "error"
    except Exception:
        return "error"


def log_hook_signal(hook, rule_id, outcome, count, hook_payload, context=""):
    """Record one privacy-safe, comparable hook effectiveness signal.

    Callers provide only stable identifiers and counts. Source text, paths,
    commands, diagnostics, and model output cannot enter this contract. The
    context itself is never stored; only its character count is retained so
    dev analysis can compare quality signal with context cost.
    """
    try:
        outcome = str(outcome)
        count = int(count)
        hook = os.path.basename(str(hook))
        rule_id = str(rule_id)
        if (
            outcome not in _HOOK_SIGNAL_OUTCOMES or count <= 0
            or _HOOK_SIGNAL_NAME_RE.fullmatch(hook) is None
            or _HOOK_SIGNAL_ID_RE.fullmatch(rule_id) is None
        ):
            return "error"
        data = {
            "hook": hook,
            "rule_id": rule_id,
            "outcome": outcome,
            "count": count,
            "context_chars": len(str(context or "")),
        }
        return log_event("hook_signal", data, hook_payload)
    except Exception:
        return "error"


def run(main_fn):
    """Exit nonzero on an internal failure so run-hook can report it safely."""
    try:
        main_fn()
    except Exception:
        sys.exit(1)
    sys.exit(0)
