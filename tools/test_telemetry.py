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
    os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = "runtime"
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
        "code_edit", {"lang": "python", "ext": ".py", "operation": "edit"},
        {"session_id": "abc", "prompt_id": "p1", "agent_id": "a1",
         "agent_type": "worker", "tool_use_id": "t1", "cwd": "/x/proj",
         "hook_event_name": "PostToolUse", "model": "claude-test"})
    assert result == "written"
    rows = _rows(db)
    assert len(rows) == 1, rows
    ts, sid, at, project, event, payload = rows[0]
    assert sid == "abc" and event == "code_edit"
    assert project.startswith("proj-")            # basename + hash, not full path
    assert "/x/proj" not in project               # full path NOT stored
    body = json.loads(payload)
    assert body == {"lang": "python", "ext": ".py", "operation": "edit"}
    with sqlite3.connect(db) as connection:
        envelope = connection.execute(
            "SELECT schema_version, prompt_id, agent_id, tool_use_id, hook_event, model, origin "
            "FROM events"
        ).fetchone()
    assert envelope == (2, "p1", "a1", "t1", "PostToolUse", "claude-test", "runtime")


def test_permission_request_is_separate_sensitive_local_data():
    db = _fresh_db()
    result = _hooklib.record_permission_request({
        "session_id": "permission-session", "permission_mode": "default",
        "tool_name": "Bash", "tool_input": {"command": "ssh internal-host"},
        "cwd": "/private/customer/project",
    })
    assert result == "written"
    assert _rows(db) == []
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT tool_input, permission_mode, decision, rule_evidence "
            "FROM permission_audit"
        ).fetchone()
    assert json.loads(row[0]) == {"command": "ssh internal-host"}
    assert row[1:] == ("default", None, "unavailable")


def test_origin_separates_runtime_test_and_model_lab_calls():
    old_db = os.environ.pop("MAINFRAME_TELEMETRY_DB", None)
    old_origin = os.environ.pop("MAINFRAME_TELEMETRY_ORIGIN", None)
    try:
        assert _hooklib._telemetry_origin({"transcript_path": "/private/session.jsonl"}) == "runtime"
        assert _hooklib._telemetry_origin({}) == "unclassified"
        os.environ["MAINFRAME_TELEMETRY_DB"] = "/tmp/test-telemetry.db"
        assert _hooklib._telemetry_origin({}) == "synthetic"
        assert _hooklib._telemetry_origin({"_telemetry_origin": "model-lab"}) == "model-lab"
    finally:
        if old_db is None:
            os.environ.pop("MAINFRAME_TELEMETRY_DB", None)
        else:
            os.environ["MAINFRAME_TELEMETRY_DB"] = old_db
        if old_origin is None:
            os.environ.pop("MAINFRAME_TELEMETRY_ORIGIN", None)
        else:
            os.environ["MAINFRAME_TELEMETRY_ORIGIN"] = old_origin


def test_schema_and_wal():
    db = _fresh_db()
    _hooklib.log_event("user_prompt", {"prompt_len": 0}, {})
    con = sqlite3.connect(db)
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal", mode
        cols = [r[1] for r in con.execute("PRAGMA table_info(events)").fetchall()]
        assert cols == [
            "id", "ts", "schema_version", "session_id", "prompt_id", "agent_id",
            "agent_type", "tool_use_id", "project", "hook_event", "model", "origin", "event", "payload",
        ], cols
        views = [row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view'"
        ).fetchall()]
        assert "hook_effectiveness" not in views
    finally:
        con.close()


def test_timestamp_is_utc_with_milliseconds():
    db = _fresh_db()
    assert _hooklib.log_event("user_prompt", {"prompt_len": 3}, {"session_id": "s"}) == "written"
    timestamp = _rows(db)[0][0]
    assert timestamp.endswith("Z") and "." in timestamp, timestamp


def test_initialization_migrates_legacy_rows_without_deleting_them():
    root = tempfile.mkdtemp()
    db = os.path.join(root, "telemetry.db")
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
            "session_id TEXT, agent_type TEXT, project TEXT, event TEXT, payload TEXT)"
        )
        connection.execute(
            "INSERT INTO events(ts, session_id, event, payload) VALUES (?,?,?,?)",
            ("2026-01-01T00:00:00", "old", "legacy_event", "{}"),
        )
    _hooklib.initialize_telemetry_db(db)
    os.environ["MAINFRAME_TELEMETRY_DB"] = db
    assert _hooklib.log_event("user_prompt", {"prompt_len": 2}, {"session_id": "new"}) == "written"
    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT schema_version, session_id, event FROM events ORDER BY id"
        ).fetchall()
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert rows == [(1, "old", "legacy_event"), (2, "new", "user_prompt")]
    assert version == 2


def test_fail_safe_bad_path():
    # Persistent sink failure is classified, not raised by the shared sink.
    root = tempfile.mkdtemp()
    blocker = os.path.join(root, "not-a-directory")
    with open(blocker, "w", encoding="utf-8") as handle:
        handle.write("x")
    os.environ["MAINFRAME_TELEMETRY_DB"] = os.path.join(blocker, "x.db")
    assert _hooklib.log_event("user_prompt", {"prompt_len": 1}, {}) == "error"


def test_privacy_rejects_unapproved_payload_fields():
    db = _fresh_db()
    # Caller mistake: banned keys passed in payload + a leaky hook_payload.
    result = _hooklib.log_event(
        "auto_permission_denied",
        {"tool_name": "Bash", "reason": "denied", "tool_input": {"command": "rm -rf /"},
         "prompt": "secret prompt", "path": "/Users/x/.ssh/id_rsa", "command": "rm -rf /",
         "message": "private message", "stderr": "private failure output"},
        {"session_id": "s", "cwd": "/p", "tool_input": {"command": "leak"},
         "prompt": "leak"},
    )
    assert result == "error"
    assert _rows(db) == []

    assert _hooklib.log_event(
        "auto_permission_denied", {"tool_name": "Bash"},
        {"session_id": "s", "cwd": "/p", "tool_input": {"command": "leak"},
         "prompt": "leak"},
    ) == "written"
    whole = " ".join(str(c) for c in _rows(db)[0])
    assert "leak" not in whole


def test_hook_signal_contract_is_raw_and_machine_aggregator_owns_the_view():
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
        assert _hooklib.log_event("user_prompt", {"prompt_len": 1}, {"session_id": "s"}) == "disabled"
        tdir = os.path.join(
            home, ".claude", "mainframe", "claude-code", "telemetry")
        assert not os.path.exists(tdir), "dir must not be created implicitly"
        os.makedirs(tdir)
        assert _hooklib.log_event("user_prompt", {"prompt_len": 1}, {"session_id": "s"}) == "written"
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
        "[_hooklib.log_event('user_prompt', {'prompt_len': i}, {'session_id': 's'}) for i in range(%d)]"
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
    assert all(r[4] == "user_prompt" for r in rows), "a landed row was malformed"


def test_ticket_uid_is_hash_not_slug():
    p = "/x/docs/tickets/630a4151-permission-classifier-unavailable-deny.md"
    uid = telemetry._ticket_uid(p)
    assert len(uid) == 12 and all(c in "0123456789abcdef" for c in uid), uid
    assert "permission" not in uid and "630a4151" not in uid       # slug / id not leaked
    assert uid == telemetry._ticket_uid(p)                          # stable: a rewrite -> same uid
    assert telemetry._ticket_uid("/x/docs/tickets/a7c5a653-other.md") != uid  # distinct ticket


def test_ticket_event_uses_honest_change_name_and_operation():
    db = _fresh_db()
    _drive_post_tool_use("/proj/docs/tickets/private-description.md", "s", "")
    rows = [row for row in _rows(db) if row[4] == "ticket_change"]
    assert len(rows) == 1
    assert json.loads(rows[0][5])["operation"] == "write"
    assert "private-description" not in " ".join(str(value) for value in rows[0])


def test_persistent_failure_reaches_common_launcher_contract():
    saved = telemetry.log_event
    try:
        telemetry.log_event = lambda *args, **kwargs: "error"
        try:
            _drive_main({
                "hook_event_name": "SessionStart", "session_id": "s", "source": "startup"
            })
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
    registered_events = {
        event for event, groups in hooks.items() for group in groups
        for item in group["hooks"] if item in telemetry_commands
    }
    assert "UserPromptSubmit" in registered_events
    assert "UserPromptExpansion" in registered_events
    assert "PostCompact" in registered_events
    session_matchers = [group["matcher"] for group in hooks["SessionStart"]]
    assert any("fork" in matcher.split("|") for matcher in session_matchers)


def test_turn_compaction_and_subagent_identity_are_recorded():
    db = _fresh_db()
    _drive_main({
        "hook_event_name": "UserPromptSubmit", "session_id": "s",
        "prompt_id": "p", "prompt": "hello",
    })
    _drive_main({
        "hook_event_name": "PostCompact", "session_id": "s", "trigger": "auto",
    })
    _drive_main({
        "hook_event_name": "SubagentStart", "session_id": "s",
        "agent_id": "a", "agent_type": "mainframe-researcher",
    })
    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT event, prompt_id, agent_id, agent_type, payload FROM events ORDER BY id"
        ).fetchall()
    assert rows[0][:2] == ("user_prompt", "p")
    assert json.loads(rows[0][4]) == {"prompt_len": 5}
    assert rows[1][0] == "compaction" and json.loads(rows[1][4]) == {"trigger": "auto"}
    assert rows[2][1:4] == ("", "a", "mainframe-researcher")


def test_skill_requests_distinguish_model_and_direct_user_paths():
    db = _fresh_db()
    _drive_main({
        "hook_event_name": "PreToolUse", "session_id": "s", "prompt_id": "p",
        "tool_use_id": "t", "tool_name": "Skill",
        "tool_input": {"skill": "mainframe:testing-strategy"},
    })
    _drive_main({
        "hook_event_name": "UserPromptExpansion", "session_id": "s", "prompt_id": "p2",
        "expansion_type": "slash_command", "command_name": "mainframe:init",
        "command_source": "plugin", "prompt": "/mainframe:init",
    })
    rows = [json.loads(row[5]) for row in _rows(db) if row[4] == "skill_request"]
    assert rows == [
        {"skill": "testing-strategy", "invoker": "model"},
        {"skill": "init", "invoker": "user"},
    ]


def test_contract_rejects_invalid_enums_and_incomplete_session_pairs():
    db = _fresh_db()
    assert _hooklib.log_event("compaction", {"trigger": "guessed"}, {}) == "error"
    assert _hooklib.log_event("session", {"phase": "start"}, {}) == "error"
    assert _hooklib.log_event(
        "session", {"phase": "end", "source": "startup", "end_reason": "other"}, {}
    ) == "error"
    assert _rows(db) == []


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
               "agent_id": "agent-1" if agent_type else "", "agent_type": agent_type,
               "prompt_id": "prompt-1", "tool_use_id": "tool-1", "tool_name": "Write",
               "duration_ms": 12, "cwd": "/proj",
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
