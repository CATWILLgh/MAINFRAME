"""Small Codex-native compatibility layer for deterministic hook checks."""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    _contract_spec = importlib.util.spec_from_file_location(
        "mainframe_codex_telemetry_contract",
        os.path.join(SCRIPT_DIR, "_telemetry_contract.py"),
    )
    if _contract_spec is None or _contract_spec.loader is None:
        raise RuntimeError("Codex telemetry contract is unavailable")
    _contract = importlib.util.module_from_spec(_contract_spec)
    _contract_spec.loader.exec_module(_contract)
    ROW_SCHEMA_VERSION = _contract.ROW_SCHEMA_VERSION
    validate_payload = _contract.validate_payload
except Exception:
    ROW_SCHEMA_VERSION = 0
    validate_payload = None

try:
    from _permission_audit import (
        initialize as initialize_permission_audit,
        record_decision as _record_permission_decision,
        record_request as _record_permission_request,
    )
except Exception:
    initialize_permission_audit = None
    _record_permission_decision = None
    _record_permission_request = None


CODE_EXTENSIONS = frozenset({
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
    ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
    ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
})

HUB_HOOK_FILES = frozenset({
    "mainframe-hook.py", "scan-suppression-markers.py",
    "stop-gate-suppression-markers.py", "python-security-scan.py",
    "python-security-stop-gate.py", "nodejs-security-scan.py",
    "nodejs-security-stop-gate.py",
    "_bash_patterns.py", "comment-discipline-reminder.py",
    "stop-gate-comment-discipline.py", "comment_extract.py",
    "_comment_findings.py", "_python_findings.py", "_node_findings.py",
    "_length_check.py",
    "length-quality-note.py", "_hooklib.py", "_markers.py",
    "_telemetry_contract.py", "telemetry.py",
    "_permission_audit.py",
    "_marker_state.py", "_notice_state.py",
})


def ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def load_payload():
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def emit_note(event, text):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": text,
        }
    }))


def emit_permission(decision, reason):
    if decision not in {"allow", "deny"}:
        raise ValueError(f"unsupported Codex PreToolUse decision: {decision}")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return reason


def emit_block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    return reason


def stop_guard_cwd(payload):
    if payload.get("stop_hook_active"):
        return None
    return payload.get("cwd") or "."


def read_git_head(file_path):
    if not file_path:
        return None
    cwd = os.path.dirname(file_path) or "."
    try:
        rel = subprocess.check_output(
            ["git", "ls-files", "--full-name", file_path], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        if not rel:
            return None
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"], cwd=cwd,
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode()
    except Exception:
        return None


_TELEMETRY_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS events ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, "
    "schema_version INTEGER NOT NULL, session_id TEXT, turn_id TEXT, "
    "agent_id TEXT, agent_type TEXT, tool_use_id TEXT, project TEXT, "
    "hook_event TEXT, model TEXT, origin TEXT NOT NULL DEFAULT 'runtime', "
    "event TEXT NOT NULL, payload TEXT NOT NULL)"
)
_TELEMETRY_RETRY_DELAYS = (0.0, 0.005, 0.015, 0.030, 0.060)
_HOOK_SIGNAL_OUTCOMES = frozenset({"noted", "asked", "blocked", "resolved"})
_HOOK_SIGNAL_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_HOOK_SIGNAL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def _telemetry_db_path():
    return (
        os.environ.get("MAINFRAME_CODEX_TELEMETRY_DB")
        or os.path.expanduser(
            "~/.codex/mainframe/codex/telemetry/telemetry.db"
        )
    )


def _telemetry_project_key(cwd):
    if not cwd:
        return ""
    normalized = os.path.normpath(str(cwd))
    base = os.path.basename(normalized)
    digest = hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:6]
    return f"{base}-{digest}"


def initialize_telemetry_db(db=None):
    path = db or _telemetry_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(_TELEMETRY_SCHEMA)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id, id)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_model_usage_sample "
            "ON events(json_extract(payload, '$.sample_id')) "
            "WHERE event = 'model_usage'"
        )
        # Every native-OTel-derived row carries a sample_id. The exporter may
        # replay a batch, so uniqueness — not arrival — decides what is stored.
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_sample "
            "ON events(json_extract(payload, '$.sample_id')) "
            "WHERE json_extract(payload, '$.sample_id') IS NOT NULL"
        )
        connection.execute(f"PRAGMA user_version={ROW_SCHEMA_VERSION}")
        connection.commit()
    finally:
        connection.close()
    if initialize_permission_audit is not None:
        initialize_permission_audit(path)
    return path


def record_permission_request(hook_payload):
    db = _telemetry_db_path()
    explicit = bool(os.environ.get("MAINFRAME_CODEX_TELEMETRY_DB"))
    if not explicit and not os.path.isfile(os.path.join(os.path.dirname(db), "enabled")):
        return "disabled"
    if _record_permission_request is None:
        return "error"
    try:
        return _record_permission_request(db, "codex", hook_payload or {})
    except Exception:
        return "error"


def record_permission_decision(sample):
    if _record_permission_decision is None:
        return "error"
    try:
        return _record_permission_decision(_telemetry_db_path(), "codex", sample or {})
    except Exception:
        return "error"


def _telemetry_busy(error):
    message = str(error).lower()
    return "locked" in message or "busy" in message


_EVENT_INSERT = (
    "INSERT INTO events(ts, schema_version, session_id, turn_id, agent_id, "
    "agent_type, tool_use_id, project, hook_event, model, origin, event, payload) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
)
_PENDING_EVENT_LIMIT = 512


def _pending_directory(db):
    return os.path.join(os.path.dirname(db), "pending-events")


def _queue_pending_row(db, row):
    try:
        directory = _pending_directory(db)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        queued = [name for name in os.listdir(directory)
                  if ".json" in name and not name.endswith(".invalid")]
        if len(queued) >= _PENDING_EVENT_LIMIT:
            return "error"
        fd, temporary = tempfile.mkstemp(prefix="event-", suffix=".tmp", dir=directory)
        final = temporary[:-4] + ".json"
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(list(row), handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return "queued"
    except Exception:
        return "error"


def _flush_pending_rows(db, limit=8):
    directory = _pending_directory(db)
    try:
        now = time.time()
        for name in os.listdir(directory):
            if ".json.claim-" not in name:
                continue
            claimed = os.path.join(directory, name)
            if now - os.path.getmtime(claimed) < 60:
                continue
            original = claimed.split(".claim-", 1)[0]
            if not os.path.exists(original):
                os.replace(claimed, original)
        names = sorted(name for name in os.listdir(directory) if name.endswith(".json"))
    except OSError:
        return
    for name in names[:limit]:
        source = os.path.join(directory, name)
        claim = source + f".claim-{os.getpid()}"
        try:
            os.replace(source, claim)
        except OSError:
            continue
        try:
            with open(claim, encoding="utf-8") as handle:
                row = json.load(handle)
            if not isinstance(row, list) or len(row) != 13:
                os.replace(claim, claim + ".invalid")
                continue
            connection = sqlite3.connect(db, timeout=0.05)
            try:
                connection.execute("PRAGMA busy_timeout=50")
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute(_EVENT_INSERT, tuple(row))
                connection.commit()
            finally:
                connection.close()
            os.unlink(claim)
        except sqlite3.IntegrityError:
            try:
                os.unlink(claim)
            except OSError:
                pass
        except Exception:
            try:
                os.replace(claim, source)
            except OSError:
                pass
            break


def log_event(event, payload=None, hook_payload=None):
    """Append one allowlisted row; telemetry failure never affects the hook."""
    try:
        db = _telemetry_db_path()
        directory = os.path.dirname(db)
        explicit = bool(os.environ.get("MAINFRAME_CODEX_TELEMETRY_DB"))
        if explicit:
            os.makedirs(directory, exist_ok=True)
        elif not os.path.isfile(os.path.join(directory, "enabled")):
            return "disabled"
        if not os.path.exists(db):
            initialize_telemetry_db(db)
        _flush_pending_rows(db)
        if validate_payload is None or ROW_SCHEMA_VERSION <= 0:
            return "error"

        envelope = hook_payload or {}
        safe = validate_payload(str(event), payload or {})
        now = datetime.datetime.now(datetime.timezone.utc)
        row = (
            now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            ROW_SCHEMA_VERSION,
            str(envelope.get("session_id") or ""),
            str(envelope.get("turn_id") or ""),
            str(envelope.get("agent_id") or ""),
            str(envelope.get("agent_type") or ""),
            str(envelope.get("tool_use_id") or ""),
            _telemetry_project_key(envelope.get("cwd") or ""),
            str(envelope.get("hook_event_name") or ""),
            str(envelope.get("model") or ""),
            (
                "runtime"
                if not explicit
                else (
                    "runtime"
                    if os.environ.get("MAINFRAME_CODEX_TELEMETRY_ORIGIN") == "runtime"
                    else "synthetic"
                )
            ),
            str(event),
            json.dumps(safe, separators=(",", ":")),
        )
        for attempt, delay in enumerate(_TELEMETRY_RETRY_DELAYS):
            if delay:
                time.sleep(delay + ((os.getpid() + attempt) % 5) / 1000)
            connection = None
            try:
                connection = sqlite3.connect(db, timeout=0.05)
                connection.execute("PRAGMA busy_timeout=50")
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute(_EVENT_INSERT, row)
                connection.commit()
                return "written"
            except sqlite3.IntegrityError:
                return "deduplicated"
            except sqlite3.OperationalError as error:
                if not _telemetry_busy(error):
                    return "error"
            finally:
                if connection is not None:
                    connection.close()
        return _queue_pending_row(db, row)
    except Exception:
        return "error"


def log_hook_signal(hook, rule_id, outcome, count, hook_payload, context=""):
    try:
        hook = os.path.basename(str(hook))
        rule_id = str(rule_id)
        outcome = str(outcome)
        count = int(count)
        if (
            _HOOK_SIGNAL_NAME_RE.fullmatch(hook) is None
            or _HOOK_SIGNAL_ID_RE.fullmatch(rule_id) is None
            or outcome not in _HOOK_SIGNAL_OUTCOMES
            or count <= 0
        ):
            return "error"
        return log_event("hook_signal", {
            "hook": hook,
            "rule_id": rule_id,
            "outcome": outcome,
            "count": count,
            "context_chars": len(str(context or "")),
        }, hook_payload)
    except Exception:
        return "error"


def run(main_fn):
    try:
        main_fn()
    except Exception:
        sys.exit(1)
    sys.exit(0)
