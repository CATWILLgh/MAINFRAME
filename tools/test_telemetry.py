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
                        "..", "adapters/claude-code/plugin", "hooks", "scripts")
sys.path.insert(0, _SCRIPTS)
import _hooklib  # noqa: E402
import telemetry  # noqa: E402


def _fresh_db():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "telemetry.db")
    os.environ["MAINFRAME_TELEMETRY_DB"] = db
    _hooklib.initialize_telemetry_db(db)
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
    result = _hooklib.log_event(
        "incident", {"hook": "h", "rule_id": "r", "file_ext": ".py"},
        {"session_id": "abc", "agent_type": "", "cwd": "/x/proj"})
    assert result == "written"
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
        views = [row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view'"
        ).fetchall()]
        assert "hook_effectiveness" in views
    finally:
        con.close()


def test_fail_safe_bad_path():
    # Persistent sink failure is classified, not raised by the shared sink.
    root = tempfile.mkdtemp()
    blocker = os.path.join(root, "not-a-directory")
    with open(blocker, "w", encoding="utf-8") as handle:
        handle.write("x")
    os.environ["MAINFRAME_TELEMETRY_DB"] = os.path.join(blocker, "x.db")
    assert _hooklib.log_event("e", {"k": 1}, {}) == "error"


def test_privacy_strips_banned_keys():
    db = _fresh_db()
    # Caller mistake: banned keys passed in payload + a leaky hook_payload.
    _hooklib.log_event(
        "permission_denied",
        {"tool_name": "Bash", "reason": "denied", "tool_input": {"command": "rm -rf /"},
         "prompt": "secret prompt", "path": "/Users/x/.ssh/id_rsa", "command": "rm -rf /",
         "message": "private message", "stderr": "private failure output"},
        {"session_id": "s", "cwd": "/p", "tool_input": {"command": "leak"},
         "prompt": "leak"},
    )
    rows = _rows(db)
    assert len(rows) == 1
    payload = rows[0][5]
    body = json.loads(payload)
    # Allowed low-risk keys survive; free-form denial reasons do not.
    assert body.get("tool_name") == "Bash"
    assert "reason" not in body
    # Banned structural keys stripped from the stored payload:
    for banned in ("tool_input", "prompt", "command", "path", "message", "stderr"):
        assert banned not in body, f"{banned} leaked into payload"
    # And nothing from hook_payload's tool_input/prompt anywhere in the row:
    whole = " ".join(str(c) for c in rows[0])
    assert "leak" not in whole and "secret prompt" not in whole and "id_rsa" not in whole


def test_hook_signal_contract_and_effectiveness_view():
    db = _fresh_db()
    hp = {"session_id": "s", "agent_type": "mainframe-test", "cwd": "/private/proj"}
    assert _hooklib.log_hook_signal(
        "/hooks/check.py", "unsafe-call", "noted", 3, hp,
        context="private diagnostic text",
    ) == "written"
    assert _hooklib.log_hook_signal(
        "/hooks/check.py", "unsafe-call", "resolved", 2, hp,
    ) == "written"
    rows = [row for row in _rows(db) if row[4] == "hook_signal"]
    assert len(rows) == 2
    first = json.loads(rows[0][5])
    assert first == {
        "hook": "check.py", "rule_id": "unsafe-call", "outcome": "noted",
        "count": 3, "context_chars": len("private diagnostic text"),
    }
    whole = " ".join(str(value) for row in rows for value in row)
    assert "private diagnostic text" not in whole and "/private/proj" not in whole
    con = sqlite3.connect(db)
    try:
        summary = con.execute(
            "SELECT hook, rule_id, signals, sessions, noted, asked, blocked, "
            "resolved, context_chars FROM hook_effectiveness"
        ).fetchone()
    finally:
        con.close()
    assert summary == (
        "check.py", "unsafe-call", 2, 1, 3, 0, 0, 2,
        len("private diagnostic text"),
    )


def test_hook_signal_rejects_unknown_or_empty_outcomes():
    db = _fresh_db()
    assert _hooklib.log_hook_signal("h.py", "r", "invented", 1, {}) == "error"
    assert _hooklib.log_hook_signal("h.py", "r", "noted", 0, {}) == "error"
    assert _hooklib.log_hook_signal("h.py", "private rule text", "noted", 1, {}) == "error"
    assert _hooklib.log_hook_signal("private hook text", "r", "noted", 1, {}) == "error"
    assert _rows(db) == []


def test_default_path_requires_existing_dir():
    # Dev-only opt-in: without the env override, log_event must neither create
    # the Claude adapter's dev directory nor write while it is absent.
    old_home = os.environ.get("HOME")
    os.environ.pop("MAINFRAME_TELEMETRY_DB", None)
    home = tempfile.mkdtemp()
    os.environ["HOME"] = home
    try:
        assert _hooklib.log_event("e", {"k": 1}, {"session_id": "s"}) == "disabled"
        tdir = os.path.join(
            home, ".claude", "mainframe", "claude-code", "telemetry")
        assert not os.path.exists(tdir), "dir must not be created implicitly"
        os.makedirs(tdir)
        assert _hooklib.log_event("e2", {}, {"session_id": "s"}) == "written"
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


def test_concurrency_writers_preserve_all_rows():
    # Real hook shape: many short-lived processes share one WAL database. The
    # bounded retry must absorb this expected burst without crashing or dropping
    # rows on the supported local filesystem.
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
    print(f"  concurrency: {got}/{n_proc * per} rows landed")
    assert all(c == 0 for c in codes), f"a writer crashed under contention: {codes}"
    assert got == n_proc * per, f"expected every row under load, got {got}"
    assert all(r[4] == "c" for r in rows), "a landed row was malformed"


def test_ticket_uid_is_hash_not_slug():
    p = "/x/docs/tickets/630a4151-permission-classifier-unavailable-deny.md"
    uid = telemetry._ticket_uid(p)
    assert len(uid) == 12 and all(c in "0123456789abcdef" for c in uid), uid
    assert "permission" not in uid and "630a4151" not in uid       # slug / id not leaked
    assert uid == telemetry._ticket_uid(p)                          # stable: a rewrite -> same uid
    assert telemetry._ticket_uid("/x/docs/tickets/a7c5a653-other.md") != uid  # distinct ticket


def test_ticket_event_stores_only_uid():
    db = _fresh_db()
    _drive_post_tool_use("/proj/docs/tickets/private-description.md", "s", "")
    rows = [row for row in _rows(db) if row[4] == "ticket_created"]
    assert len(rows) == 1
    assert set(json.loads(rows[0][5])) == {"uid"}
    assert "private-description" not in " ".join(str(value) for value in rows[0])


def test_persistent_failure_reaches_common_launcher_contract():
    saved = telemetry.log_event
    try:
        telemetry.log_event = lambda *args, **kwargs: "error"
        try:
            _drive_main({"hook_event_name": "SessionStart", "session_id": "s"})
        except RuntimeError as exc:
            assert "sink unavailable" in str(exc)
        else:
            raise AssertionError("persistent failure was swallowed")
    finally:
        telemetry.log_event = saved


def test_every_telemetry_registration_uses_early_gate():
    path = os.path.join(_SCRIPTS, "..", "hooks.json")
    with open(path, encoding="utf-8") as handle:
        hooks = json.load(handle)["hooks"]
    telemetry_commands = []
    for groups in hooks.values():
        for group in groups:
            telemetry_commands.extend(
                item for item in group["hooks"]
                if item["args"][-1].endswith("/telemetry.py"))
    assert telemetry_commands
    assert all(item["args"][0].endswith("/run-telemetry-hook.sh")
               for item in telemetry_commands)


def test_early_gate_starts_no_runtime_without_dev_marker():
    wrapper = os.path.join(_SCRIPTS, "run-telemetry-hook.sh")
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, HOME=home, TMPDIR=tmp)
        env.pop("MAINFRAME_TELEMETRY_DB", None)
        proc = subprocess.run(
            ["sh", wrapper, "SessionStart", "/definitely/missing.py"],
            input="{}", text=True, capture_output=True, env=env,
        )
        assert proc.returncode == 0 and proc.stdout == "" and proc.stderr == ""
        assert os.listdir(tmp) == [], "disabled gate must not create launcher temp files"


def test_skill_name_normalized():
    assert telemetry._norm_skill("mainframe:init") == "init"
    assert telemetry._norm_skill("init") == "init"
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
                         "mainframe-react-frontend-engineer")
    rows = [r for r in _rows(db) if r[4] == "code_edit"]
    assert len(rows) == 1, rows
    _, sid, at, _, _, payload = rows[0]
    assert sid == "s1" and at == "mainframe-react-frontend-engineer"
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
