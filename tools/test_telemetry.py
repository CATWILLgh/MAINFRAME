#!/usr/bin/env python3
"""Unit tests for the `_hooklib.log_event` telemetry sink.

Run: `python3 tools/test_telemetry.py` (exit 0 = pass). Stdlib only. Uses a temp
DB via the `MAINFRAME_TELEMETRY_DB` env var so the real `~/.claude` DB is never
touched. The concurrency test spawns real subprocesses — the actual hook scenario.
"""

import io
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
    except sqlite3.OperationalError:
        return []                       # no row was ever logged -> table absent
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


def _drive_main(payload):
    saved = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        telemetry.main()
    finally:
        sys.stdin = saved


def test_todo_write_logs_counts_not_content():
    db = _fresh_db()
    _drive_main({
        "hook_event_name": "PreToolUse",
        "tool_name": "TodoWrite",
        "session_id": "s",
        "tool_input": {"todos": [
            {"content": "secret task detail", "status": "completed", "activeForm": "a"},
            {"content": "another", "status": "in_progress", "activeForm": "b"},
            {"content": "third", "status": "pending", "activeForm": "c"},
        ]},
    })
    rows = _rows(db)
    assert len(rows) == 1, rows
    assert rows[0][4] == "todo_write"
    assert json.loads(rows[0][5]) == {"n": 3, "pending": 1, "in_progress": 1, "completed": 1}
    # todo content (task descriptions) must never be logged
    whole = " ".join(str(c) for c in rows[0])
    assert "secret task detail" not in whole and "another" not in whole


def test_concurrency_writers_never_raise_and_write():
    # Telemetry is best-effort by design: under write contention SQLite may fail to
    # acquire the lock within the 50ms busy_timeout, and log_event silently drops
    # that row — it must never stall or crash the agent. So the contract under load
    # is behavioural, not a hit-rate: (1) no writer ever propagates an exception,
    # (2) the mechanism still writes — rows accumulate across contending processes.
    # A percentage threshold would couple the test to filesystem speed and flake on
    # a slow runner; an absolute floor that only catches a fully-broken sink does not.
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
    codes = [p.wait() for p in procs]
    rows = _rows(db)
    got = len(rows)
    print(f"  concurrency: {got}/{n_proc * per} rows landed "
          f"(drops under contention are by-design, not asserted)")
    assert all(c == 0 for c in codes), f"a writer crashed under contention: {codes}"
    assert got >= per, f"sink should land >= {per} rows under load, got {got}"
    assert all(r[4] == "c" for r in rows), "a landed row was malformed"


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


def test_lang_bucket_maps_profile_domains():
    assert telemetry._lang_bucket("/x/app/Widget.tsx") == "frontend"
    assert telemetry._lang_bucket("/x/app/Widget.jsx") == "frontend"
    assert telemetry._lang_bucket("/x/styles/main.scss") == "frontend"
    assert telemetry._lang_bucket("/x/src/service.ts") == "ts"
    assert telemetry._lang_bucket("/x/types/foo.d.ts") == "ts"
    assert telemetry._lang_bucket("/x/api/handler.py") == "python"


def test_lang_bucket_skips_noncode():
    # Non-profile-eligible files return None -> not logged, keeping code_edit a clean
    # denominator for profile-agent under-use.
    for p in ("/x/README.md", "/x/config.json", "/x/data.yaml", "/x/Makefile", "/x/go.mod"):
        assert telemetry._lang_bucket(p) is None, p


def _drive_post_tool_use(file_path, session, agent_type):
    payload = {"hook_event_name": "PostToolUse", "session_id": session,
               "agent_type": agent_type, "cwd": "/proj",
               "tool_input": {"file_path": file_path}}
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        telemetry.main()
    finally:
        sys.stdin = old


def test_code_edit_logged_with_subagent_attribution():
    db = _fresh_db()
    _drive_post_tool_use("/proj/src/Widget.tsx", "s1",
                         "mainframe:react-frontend-engineer")
    rows = [r for r in _rows(db) if r[4] == "code_edit"]
    assert len(rows) == 1, rows
    _, sid, at, _, _, payload = rows[0]
    assert sid == "s1" and at == "mainframe:react-frontend-engineer"
    body = json.loads(payload)
    assert body["lang"] == "frontend" and body["ext"] == ".tsx"


def test_code_edit_main_agent_empty_attribution():
    db = _fresh_db()
    _drive_post_tool_use("/proj/api/main.py", "s2", "")
    rows = [r for r in _rows(db) if r[4] == "code_edit"]
    assert len(rows) == 1 and rows[0][2] == ""        # main agent -> empty agent_type
    assert json.loads(rows[0][5])["lang"] == "python"


def test_noncode_edit_writes_no_code_edit_row():
    db = _fresh_db()
    _drive_post_tool_use("/proj/notes.md", "s3", "")
    assert not [r for r in _rows(db) if r[4] == "code_edit"]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK telemetry — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
