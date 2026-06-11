#!/usr/bin/env python3
"""Unit tests for the `_hooklib.log_event` telemetry sink.

Run: `python3 tools/test_telemetry.py` (exit 0 = pass). Stdlib only. Uses a temp
DB via the `MAINFRAME_TELEMETRY_DB` env var so the real `~/.claude` DB is never
touched. The concurrency test spawns real subprocesses — the actual hook scenario.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile

_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "plugin-dist", "hooks", "scripts")
sys.path.insert(0, _SCRIPTS)
import _hooklib
import telemetry


def _fresh_db():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "telemetry.db")
    os.environ["MAINFRAME_TELEMETRY_DB"] = db
    return db


def _rows(db):
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "SELECT ts, session_id, agent_type, project, event, payload FROM events"
        ).fetchall()
    finally:
        con.close()


def test_writes_row():
    db = _fresh_db()
    _hooklib.log_event("incident", {"hook": "h", "rule_id": "r", "file_ext": ".py"},
                       {"session_id": "abc", "agent_type": "", "cwd": "/x/proj"})
    rows = _rows(db)
    assert len(rows) == 1, rows
    ts, sid, at, project, event, payload = rows[0]
    assert sid == "abc" and event == "incident"
    assert project.startswith("proj-")            # basename + hash, not full path
    assert "/x/proj" not in project               # full path NOT stored
    body = json.loads(payload)
    assert body["rule_id"] == "r" and body["file_ext"] == ".py"


def test_schema_and_wal():
    db = _fresh_db()
    _hooklib.log_event("e", {}, {})
    con = sqlite3.connect(db)
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal", mode
        cols = [r[1] for r in con.execute("PRAGMA table_info(events)").fetchall()]
        assert cols == ["id", "ts", "session_id", "agent_type", "project", "event", "payload"], cols
    finally:
        con.close()


def test_fail_safe_bad_path():
    # Unwritable DB path -> silent no-op, never raises.
    os.environ["MAINFRAME_TELEMETRY_DB"] = "/this/path/does/not/exist/x.db"
    _hooklib.log_event("e", {"k": 1}, {})   # must not raise


def test_privacy_strips_banned_keys():
    db = _fresh_db()
    # Caller mistake: banned keys passed in payload + a leaky hook_payload.
    _hooklib.log_event(
        "permission_denied",
        {"tool_name": "Bash", "reason": "denied", "tool_input": {"command": "rm -rf /"},
         "prompt": "secret prompt", "path": "/Users/x/.ssh/id_rsa", "command": "rm -rf /"},
        {"session_id": "s", "cwd": "/p", "tool_input": {"command": "leak"},
         "prompt": "leak"},
    )
    rows = _rows(db)
    assert len(rows) == 1
    payload = rows[0][5]
    body = json.loads(payload)
    # Allowed low-risk keys survive:
    assert body.get("tool_name") == "Bash" and body.get("reason") == "denied"
    # Banned structural keys stripped from the stored payload:
    for banned in ("tool_input", "prompt", "command", "path"):
        assert banned not in body, f"{banned} leaked into payload"
    # And nothing from hook_payload's tool_input/prompt anywhere in the row:
    whole = " ".join(str(c) for c in rows[0])
    assert "leak" not in whole and "secret prompt" not in whole and "id_rsa" not in whole


def test_default_path_requires_existing_dir():
    # Dev-only opt-in: without the env override, log_event must neither create
    # ~/.claude/mainframe/telemetry nor write anything while the dir is absent.
    old_home = os.environ.get("HOME")
    os.environ.pop("MAINFRAME_TELEMETRY_DB", None)
    home = tempfile.mkdtemp()
    os.environ["HOME"] = home
    try:
        _hooklib.log_event("e", {"k": 1}, {"session_id": "s"})
        tdir = os.path.join(home, ".claude", "mainframe", "telemetry")
        assert not os.path.exists(tdir), "dir must not be created implicitly"
        os.makedirs(tdir)
        _hooklib.log_event("e2", {}, {"session_id": "s"})
        assert os.path.exists(os.path.join(tdir, "telemetry.db")), \
            "opted-in (dir exists) -> row written"
    finally:
        os.environ["HOME"] = old_home


def test_concurrency_16_writers():
    db = _fresh_db()
    n_proc, per = 16, 25
    worker = (
        "import sys; sys.path.insert(0, %r); import _hooklib;\n"
        "[_hooklib.log_event('c', {'i': i}, {'session_id': 's'}) for i in range(%d)]"
        % (_SCRIPTS, per)
    )
    env = dict(os.environ, MAINFRAME_TELEMETRY_DB=db)
    procs = [subprocess.Popen([sys.executable, "-c", worker], env=env)
             for _ in range(n_proc)]
    for p in procs:
        p.wait()
    got = len(_rows(db))
    expected = n_proc * per
    rate = got / expected
    print(f"  concurrency: {got}/{expected} rows landed ({rate:.1%}); drop {1 - rate:.1%}")
    # WAL + 50ms busy_timeout should land the vast majority; drops are acceptable
    # but must be the exception, not the rule.
    assert rate >= 0.90, f"too many drops: {got}/{expected}"


def test_ticket_uid_is_hash_not_slug():
    p = "/x/docs/tickets/630a4151-permission-classifier-unavailable-deny.md"
    uid = telemetry._ticket_uid(p)
    assert len(uid) == 12 and all(c in "0123456789abcdef" for c in uid), uid
    assert "permission" not in uid and "630a4151" not in uid       # slug / id not leaked
    assert uid == telemetry._ticket_uid(p)                          # stable: a rewrite -> same uid
    assert telemetry._ticket_uid("/x/docs/tickets/a7c5a653-other.md") != uid  # distinct ticket


def test_skill_name_normalized():
    assert telemetry._norm_skill("mainframe:task-workflow") == "task-workflow"
    assert telemetry._norm_skill("task-workflow") == "task-workflow"
    assert telemetry._norm_skill("") == ""


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK telemetry — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
