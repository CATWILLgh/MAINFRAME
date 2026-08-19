#!/usr/bin/env python3
"""Behavior and delivery tests for MAINFRAME's native Codex hook layer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "adapters" / "codex"
HOOK = ADAPTER / "hooks" / "scripts" / "mainframe-hook.py"
HOOKS_SOURCE = ADAPTER / "hooks" / "hooks.json"
MANAGER = ADAPTER / "scripts" / "manage-hooks.py"
PYTHON_SCAN = ADAPTER / "hooks" / "scripts" / "python-security-scan.py"
PYTHON_STOP = ADAPTER / "hooks" / "scripts" / "python-security-stop-gate.py"
NODE_SCAN = ADAPTER / "hooks" / "scripts" / "nodejs-security-scan.py"
NODE_STOP = ADAPTER / "hooks" / "scripts" / "nodejs-security-stop-gate.py"


def _state_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "MAINFRAME_CODEX_SNAPSHOT_DIR": str(root / "snapshots"),
        "MAINFRAME_MARKER_STATE_DIR": str(root / "markers"),
        "MAINFRAME_NOTICE_STATE_DIR": str(root / "notices"),
        # A developer may have live Codex telemetry enabled globally. Every
        # synthetic hook invocation must still remain inside its temporary test
        # root instead of contaminating the user's Observatory history.
        "MAINFRAME_CODEX_TELEMETRY_DB": str(root / "telemetry" / "telemetry.db"),
    })
    return env


def _run_hook(
    payload: dict, state: Path, *, extra_env: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess, dict | None]:
    env = _state_env(state)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    output = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc, output


def _run_python_hook(payload: dict, state: Path) -> tuple[subprocess.CompletedProcess, dict | None]:
    script = PYTHON_STOP if payload["hook_event_name"] == "SubagentStop" else PYTHON_SCAN
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env=_state_env(state),
    )
    output = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc, output


def _run_node_hook(payload: dict, state: Path) -> tuple[subprocess.CompletedProcess, dict | None]:
    script = NODE_STOP if payload["hook_event_name"] == "SubagentStop" else NODE_SCAN
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=_state_env(state),
    )
    output = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc, output


def _python_edit_payload(
    root: Path, source: Path, old: str, new: str, *, session: str = "python",
    agent: str = "python-child",
) -> dict:
    source.write_text(new, encoding="utf-8")
    return {
        "session_id": session,
        "turn_id": "turn",
        "agent_id": agent,
        "agent_type": "mainframe_python_backend_engineer",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "cwd": str(root),
        "tool_input": {
            "file_path": str(source),
            "old_string": old,
            "new_string": new,
        },
    }


def _python_stop_payload(root: Path, *, session: str = "python", agent: str = "python-child") -> dict:
    return {
        "session_id": session,
        "turn_id": "turn",
        "agent_id": agent,
        "agent_type": "mainframe_python_backend_engineer",
        "hook_event_name": "SubagentStop",
        "cwd": str(root),
        "stop_hook_active": False,
    }


def _node_edit_payload(
    root: Path, source: Path, old: str, new: str, *, session: str = "node",
    agent: str = "node-child",
) -> dict:
    source.write_text(new, encoding="utf-8")
    return {
        "session_id": session,
        "turn_id": "turn",
        "agent_id": agent,
        "agent_type": "mainframe_typescript_backend_engineer",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "cwd": str(root),
        "tool_input": {
            "file_path": str(source),
            "old_string": old,
            "new_string": new,
        },
    }


def _node_stop_payload(root: Path, *, session: str = "node", agent: str = "node-child") -> dict:
    return {
        "session_id": session,
        "turn_id": "turn",
        "agent_id": agent,
        "agent_type": "mainframe_typescript_backend_engineer",
        "hook_event_name": "SubagentStop",
        "cwd": str(root),
        "stop_hook_active": False,
    }


def _tool_payload(
    root: Path, *, event: str, session: str = "session", agent: str = "",
    tool_use: str = "tool", command: str = "", tool_name: str = "Bash",
) -> dict:
    return {
        "session_id": session,
        "turn_id": "turn",
        "agent_id": agent,
        "agent_type": "worker" if agent else "",
        "tool_use_id": tool_use,
        "hook_event_name": event,
        "tool_name": tool_name,
        "cwd": str(root),
        "tool_input": {"command": command},
    }


def _patch_payload(
    root: Path, filename: str, *, event: str, session: str = "session",
    agent: str = "", tool_use: str = "tool",
) -> dict:
    command = (
        "*** Begin Patch\n"
        f"*** Update File: {filename}\n"
        "*** End Patch"
    )
    return _tool_payload(
        root, event=event, session=session, agent=agent, tool_use=tool_use,
        command=command, tool_name="apply_patch",
    )


def _numbered_lines(count: int) -> str:
    return "".join(f"value_{index} = {index}\n" for index in range(count))


def _synthetic_github_token() -> str:
    return "ghp_" + "0123456789abcdefghijklmnopqrstuvwxyz"[:36]


def _git_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=root, check=True
    )
    return root


def test_hook_source_is_one_handler_per_event_and_has_bounded_outputs():
    source = json.loads(HOOKS_SOURCE.read_text(encoding="utf-8"))
    assert source["description"].startswith("MAINFRAME lifecycle")
    assert set(source["hooks"]) == {
        "SessionStart", "SessionEnd", "SubagentStart", "PreToolUse",
        "PermissionRequest", "PostToolUse", "PostCompact",
        "UserPromptSubmit", "Stop", "SubagentStop",
    }
    for event, groups in source["hooks"].items():
        assert len(groups) == 1
        assert len(groups[0]["hooks"]) == 1
        handler = groups[0]["hooks"][0]
        assert handler["type"] == "command"
        assert handler["statusMessage"].startswith("MAINFRAME:")
        assert "mainframe-hook.py" not in handler["command"]
        assert "@MAINFRAME_HOOK_SCRIPT@" in handler["command"]
        assert 0 < handler["timeout"] <= 210
        if "additionalContextLimit" in handler:
            assert 0 < handler["additionalContextLimit"] <= 1600
        else:
            assert event in {
                "SessionEnd", "SubagentStart", "PermissionRequest",
                "PostCompact", "UserPromptSubmit", "Stop", "SubagentStop",
            }
        assert "async" not in handler
    assert source["hooks"]["SessionStart"][0]["matcher"] == (
        "^(startup|resume|clear|compact)$"
    )
    assert source["hooks"]["SessionEnd"][0]["hooks"][0]["timeout"] == 3


def test_dispatcher_records_privacy_safe_dev_telemetry():
    root = Path(tempfile.mkdtemp())
    db = root / "telemetry" / "telemetry.db"
    payload = {
        "session_id": "session",
        "turn_id": "turn",
        "hook_event_name": "UserPromptSubmit",
        "permission_mode": "auto",
        "model": "gpt-test",
        "cwd": str(root / "private-project"),
        "prompt": "secret-looking prompt text that must not be stored",
    }
    proc, result = _run_hook(
        payload, root / "state",
        extra_env={"MAINFRAME_CODEX_TELEMETRY_DB": str(db)},
    )
    assert proc.returncode == 0 and result is None
    import sqlite3
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT model, event, payload, project FROM events ORDER BY id LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row[0] == "gpt-test"
    assert "secret-looking" not in " ".join(str(value) for value in row)
    assert str(root) not in " ".join(str(value) for value in row)


def test_dispatcher_records_code_edits_like_the_claude_adapter():
    root = Path(tempfile.mkdtemp())
    project = root / "project"
    (project / ".git").mkdir(parents=True)
    edited = project / "module.py"
    edited.write_text("VALUE = 1\n", encoding="utf-8")
    ignored = project / "notes.md"
    ignored.write_text("# notes\n", encoding="utf-8")
    db = root / "telemetry" / "telemetry.db"

    def edit(path):
        return {
            "session_id": "session",
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"file_path": str(path)},
            "cwd": str(project),
        }

    for target in (edited, ignored):
        proc, _result = _run_hook(
            edit(target), root / "state",
            extra_env={"MAINFRAME_CODEX_TELEMETRY_DB": str(db)},
        )
        assert proc.returncode == 0

    import sqlite3
    with sqlite3.connect(db) as connection:
        rows = connection.execute(
            "SELECT payload FROM events WHERE event = 'code_edit' ORDER BY id"
        ).fetchall()
    # Only languages a profile sub-agent owns are bucketed, so `code_edit` stays
    # a comparable denominator across both adapters; markdown is not one.
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload == {"lang": "python", "ext": ".py", "operation": "apply_patch"}


def test_startup_health_covers_every_runtime_module():
    spec = importlib.util.spec_from_file_location("mainframe_hook_test", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = {
        path.name
        for path in HOOK.parent.glob("*.py")
        if path.name != HOOK.name
    }
    assert set(module.HEALTH_MODULES) == expected
    dispatcher = HOOK.read_text(encoding="utf-8")
    assert "fallow-quality-note.py" not in dispatcher
    assert not (HOOK.parent / "fallow-quality-note.py").exists()
    assert not (HOOK.parent / "_fallow_state.py").exists()

    root = Path(tempfile.mkdtemp())
    proc, result = _run_hook(
        {
            "session_id": "health",
            "hook_event_name": "SessionStart",
            "cwd": str(root),
            "source": "startup",
        },
        root / "state",
    )
    assert proc.returncode == 0, proc.stderr
    assert result is None

    original_load = module._load_module
    failed_module = [module.HEALTH_MODULES[0]]
    module._load_module = lambda filename: (
        (_ for _ in ()).throw(ImportError("probe"))
        if filename == failed_module[0]
        else original_load(filename)
    )
    old_notice_root = os.environ.get("MAINFRAME_NOTICE_STATE_DIR")
    os.environ["MAINFRAME_NOTICE_STATE_DIR"] = str(root / "notices")
    try:
        payload = {"session_id": "health", "agent_id": ""}
        first = io.StringIO()
        with redirect_stdout(first):
            module._health(payload)
        failure = json.loads(first.getvalue())
        assert failed_module[0] in failure["systemMessage"]
        assert failed_module[0] in (
            failure["hookSpecificOutput"]["additionalContext"]
        )

        repeated = io.StringIO()
        with redirect_stdout(repeated):
            module._health(payload)
        assert repeated.getvalue() == ""

        failed_module[0] = module.HEALTH_MODULES[1]
        changed = io.StringIO()
        with redirect_stdout(changed):
            module._health(payload)
        changed_failure = json.loads(changed.getvalue())
        assert failed_module[0] in changed_failure["systemMessage"]
    finally:
        module._load_module = original_load
        if old_notice_root is None:
            os.environ.pop("MAINFRAME_NOTICE_STATE_DIR", None)
        else:
            os.environ["MAINFRAME_NOTICE_STATE_DIR"] = old_notice_root


def test_parallel_startup_health_failure_is_reported_once():
    root = Path(tempfile.mkdtemp())
    runtime = root / "runtime"
    shutil.copytree(
        HOOK.parent, runtime, ignore=shutil.ignore_patterns("__pycache__")
    )
    (runtime / "_bash_patterns.py").write_text(
        "raise ImportError('parallel startup probe')\n", encoding="utf-8"
    )
    hook = runtime / HOOK.name
    state = root / "state"
    payload = {
        "session_id": "parallel-health",
        "hook_event_name": "SessionStart",
        "cwd": str(root),
        "source": "compact",
    }

    def invoke(_index: int) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            env=_state_env(state),
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(invoke, range(16)))

    assert all(result.returncode == 0 for result in results)
    visible = [result.stdout for result in results if result.stdout.strip()]
    assert len(visible) == 1
    output = json.loads(visible[0])
    assert "_bash_patterns.py" in output["systemMessage"]
    assert "_bash_patterns.py" in (
        output["hookSpecificOutput"]["additionalContext"]
    )


def test_manager_merges_user_groups_and_uninstall_removes_only_owned_groups():
    root = Path(tempfile.mkdtemp())
    target = root / "hooks.json"
    state = root / "state.json"
    user_group = {
        "matcher": "^Bash$",
        "hooks": [{"type": "command", "command": "python3 user-hook.py"}],
    }
    target.write_text(
        json.dumps({"description": "user", "hooks": {"PreToolUse": [user_group]}}),
        encoding="utf-8",
    )
    install = subprocess.run(
        [
            sys.executable, str(MANAGER), "install", "--target", str(target),
            "--source", str(HOOKS_SOURCE), "--script", str(HOOK),
            "--state", str(state),
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert install.returncode == 0, install.stderr
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert installed["description"] == "user"
    assert user_group in installed["hooks"]["PreToolUse"]
    assert state.is_file()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.stat().st_mode) == 0o600

    reinstall = subprocess.run(
        [
            sys.executable, str(MANAGER), "install", "--target", str(target),
            "--source", str(HOOKS_SOURCE), "--script", str(HOOK),
            "--state", str(state),
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert reinstall.returncode == 0, reinstall.stderr
    current = json.loads(target.read_text(encoding="utf-8"))
    assert current["hooks"]["PreToolUse"].count(user_group) == 1

    remove = subprocess.run(
        [
            sys.executable, str(MANAGER), "uninstall", "--target", str(target),
            "--source", str(HOOKS_SOURCE), "--script", str(HOOK),
            "--state", str(state),
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert remove.returncode == 0, remove.stderr
    restored = json.loads(target.read_text(encoding="utf-8"))
    assert restored == {"description": "user", "hooks": {"PreToolUse": [user_group]}}
    assert not state.exists()


def test_manager_refuses_to_remove_a_changed_owned_group():
    root = Path(tempfile.mkdtemp())
    target = root / "hooks.json"
    state = root / "state.json"
    args = [
        "--target", str(target), "--source", str(HOOKS_SOURCE),
        "--script", str(HOOK), "--state", str(state),
    ]
    installed = subprocess.run(
        [sys.executable, str(MANAGER), "install", *args],
        capture_output=True, text=True, timeout=10,
    )
    assert installed.returncode == 0, installed.stderr
    document = json.loads(target.read_text(encoding="utf-8"))
    document["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 1
    target.write_text(json.dumps(document), encoding="utf-8")
    removed = subprocess.run(
        [sys.executable, str(MANAGER), "uninstall", *args],
        capture_output=True, text=True, timeout=10,
    )
    assert removed.returncode != 0
    assert "changed or is duplicated" in removed.stderr
    assert target.exists() and state.exists()


def test_command_safety_keeps_native_mode_authoritative_except_catastrophic_roots():
    root = Path(tempfile.mkdtemp())
    state = root / "state"

    _, ordinary_delete = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm one-file.txt"), state
    )
    assert ordinary_delete is None

    for command in (
        "rm -rf generated",
        "/bin/rm -R generated",
        "rm --recursive generated",
        "rm -rf -- generated",
        "rm -rf 'generated directory'",
        "rm -rf generated-one generated-two",
    ):
        _, reviewed_recursive = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert reviewed_recursive is None, command

    for command in (
        "rm -rf /",
        "rm -rf .",
        f"rm -rf {Path.home()}",
        "rm -rf $HOME",
        "sh -c 'rm -rf /'",
    ):
        _, catastrophic = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert catastrophic["hookSpecificOutput"]["permissionDecision"] == "deny", command

    for command in (
        "rm -f -r generated",
        "rm -rf ..",
        "rm -rf ../outside-project",
        "rm -rf /tmp/external",
        "rm -rf '$HOME/generated'",
        "rm -rf generated/*",
        "cd generated && rm -rf nested",
        "rm -rf generated >/dev/null",
        "rm -rf generated 2>/dev/null",
        "rm -rf generated & echo done",
        "if true; then rm -rf generated; fi",
        "command rm -rf generated",
        "/usr/bin/rm -rf generated",
        "find generated -exec rm -rf {} +",
        "xargs rm -rf",
    ):
        _, native_review = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert native_review is None, command

    for command in (
        "rm -rf generated && echo done",
        "rm -rf generated || echo missing",
        "rm -rf generated; echo done",
        "rm -rf generated | cat",
    ):
        _, native_review = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert native_review is None, command

    for command in (
        "echo rm -rf /",
        "printf '%s\\n' 'rm -rf /'",
        "rg 'rm -rf' .",
        "rm -f one-file.txt",
        "unlink one-file.txt",
        "rmdir empty-directory",
    ):
        _, ordinary = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert ordinary is None, command
    _, normal_push = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git push"), state
    )
    assert normal_push is None

    for command in (
        "git clean -n",
        "git clean --dry-run",
        "git clean -f",
        "git clean -fd",
        "git clean --interactive",
        "git worktree prune --dry-run",
        "git worktree prune -n",
    ):
        _, classified = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert classified is None, command

    for command in (
        "git clean -n",
        "git clean -ndx",
        "git clean --dry-run -d",
        "git worktree prune -n",
        "git worktree prune --dry-run --expire now",
        "git clean -fd",
        "git worktree prune",
        "git -C ../outside clean -n",
        "git clean -n; echo unsafe",
    ):
        _, undecided = _run_hook(
            _tool_payload(root, event="PermissionRequest", command=command), state
        )
        assert undecided is None, command

    _, rule_branch = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git branch -d old"), state
    )
    assert rule_branch is None

    _, positional_branch = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git branch new"), state
    )
    assert positional_branch is None

    _, force_push = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git push --force"), state
    )
    assert force_push["hookSpecificOutput"]["permissionDecision"] == "deny"

    _, child_commit = _run_hook(
        _tool_payload(
            root, event="PreToolUse", command="git commit -m test", agent="child"
        ),
        state,
    )
    assert child_commit["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "primary session" in child_commit["hookSpecificOutput"]["permissionDecisionReason"]

    _, primary_add = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git add example.py"), state
    )
    assert primary_add is None

    _, primary_commit = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git commit -m test"), state
    )
    assert primary_commit is None

    for command in (
        "git update-index --refresh",
        "git apply --cached change.patch",
        "git update-ref refs/heads/example HEAD",
        "git read-tree HEAD~1",
    ):
        _, reviewed = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert reviewed is None, command

    for command in (
        "git update-index file.py",
        "git apply --index change.patch",
        "git read-tree HEAD~1",
        "git commit-tree deadbeef -m test",
    ):
        _, child_delivery = _run_hook(
            _tool_payload(
                root, event="PreToolUse", command=command, agent="child"
            ),
            state,
        )
        assert child_delivery["hookSpecificOutput"]["permissionDecision"] == "deny", command
        assert "primary session" in child_delivery["hookSpecificOutput"]["permissionDecisionReason"], command

    for command in (
        "command git update-index file.py",
        "git apply --verbose --cached change.patch",
        "git -C repo update-ref refs/heads/example HEAD",
    ):
        _, indirect = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert indirect is None, command

    for command in (
        "git commit-tree deadbeef -m test",
        "git send-pack origin refs/heads/main",
        "git symbolic-ref HEAD refs/heads/other",
    ):
        _, bypass = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert bypass["hookSpecificOutput"]["permissionDecision"] == "deny", command

    for command in (
        "git symbolic-ref HEAD",
        "git apply --check --cached change.patch",
    ):
        _, inspection = _run_hook(
            _tool_payload(root, event="PreToolUse", command=command), state
        )
        assert inspection is None, command


def test_recursive_delete_allows_external_symlink_but_protects_project_root_target():
    root = Path(tempfile.mkdtemp())
    outside = Path(tempfile.mkdtemp())
    link = root / "external-link"
    link.symlink_to(outside, target_is_directory=True)
    state = root / "state"

    _, link_only = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -rf external-link"),
        state,
    )
    assert link_only is None

    _, followed_external_link = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -rf external-link/"),
        state,
    )
    assert followed_external_link is None

    project_link = root / "project-root-link"
    project_link.symlink_to(root, target_is_directory=True)
    _, followed_project_link = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -rf project-root-link/"),
        state,
    )
    assert followed_project_link["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_secret_commit_gate_checks_real_index_without_exposing_the_value():
    root = _git_repo()
    state = root / "state"
    token = _synthetic_github_token()
    source = root / ".env"
    source.write_text(f"TOKEN={token}\n", encoding="utf-8")
    subprocess.run(["git", "add", ".env"], cwd=root, check=True)

    _, blocked = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git commit -m secret"),
        state,
    )
    reason = blocked["hookSpecificOutput"]["permissionDecisionReason"]
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "github_pat" in reason and ".env" in reason
    assert token not in reason


def test_secret_commit_gate_leaves_clean_commit_and_dry_run_alone():
    root = _git_repo()
    state = root / "state"
    clean = root / "clean.txt"
    clean.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "clean.txt"], cwd=root, check=True)
    _, ordinary = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git commit -m clean"),
        state,
    )
    assert ordinary is None

    secret = root / ".env"
    secret.write_text(
        f"TOKEN={_synthetic_github_token()}\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", ".env"], cwd=root, check=True)
    _, dry_run = _run_hook(
        _tool_payload(
            root, event="PreToolUse", command="git commit --dry-run"
        ),
        state,
    )
    assert dry_run is None


def test_ripgrep_reminder_is_context_only_and_once_per_recipient():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    payload = _tool_payload(root, event="PreToolUse", command="rg -rn needle .")
    _, first = _run_hook(payload, state)
    _, second = _run_hook(payload, state)
    assert "additionalContext" in first["hookSpecificOutput"]
    assert "permissionDecision" not in first["hookSpecificOutput"]
    assert second is None


def test_current_edit_is_reported_once_and_unresolved_residue_blocks_stop():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "example.go"
    source.write_text("package example\n", encoding="utf-8")
    pre = _patch_payload(root, source.name, event="PreToolUse")
    proc, result = _run_hook(pre, state)
    assert proc.returncode == 0 and result is None

    source.write_text("package example\n// TODO phase 1\n", encoding="utf-8")
    post = _patch_payload(root, source.name, event="PostToolUse")
    proc, result = _run_hook(post, state)
    assert proc.returncode == 0
    context = result["hookSpecificOutput"]["additionalContext"]
    assert context.count("unfinished-code or diagnostic residue") == 1
    assert "example.go" in context
    assert "TODO phase 1" not in context
    assert len(context) < 4000

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert blocked["decision"] == "block"
    assert "TODO/FIXME/HACK/XXX" in blocked["reason"]
    assert "example.go" in blocked["reason"]
    assert "1 unfinished-code or diagnostic finding" in blocked["reason"]
    assert "TODO phase 1" not in blocked["reason"]

    stop["stop_hook_active"] = True
    _, loop_guard = _run_hook(stop, state)
    assert loop_guard is None


def test_later_edit_resolves_owned_residue_without_scanning_old_project_debt():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "example.go"
    source.write_text("package example\n// TODO inherited\n", encoding="utf-8")

    first_pre = _patch_payload(root, source.name, event="PreToolUse", tool_use="one")
    _run_hook(first_pre, state)
    source.write_text(
        "package example\n// TODO inherited\n// TODO introduced\n", encoding="utf-8"
    )
    first_post = _patch_payload(root, source.name, event="PostToolUse", tool_use="one")
    _, noted = _run_hook(first_post, state)
    assert noted is not None

    second_pre = _patch_payload(root, source.name, event="PreToolUse", tool_use="two")
    _run_hook(second_pre, state)
    source.write_text("package example\n// TODO inherited\n", encoding="utf-8")
    second_post = _patch_payload(root, source.name, event="PostToolUse", tool_use="two")
    _, resolved = _run_hook(second_post, state)
    assert resolved is None

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, result = _run_hook(stop, state)
    assert result is None


def test_suppression_gate_counts_identical_findings_in_multiple_files():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    sources = [root / "one.go", root / "two.go"]
    for index, source in enumerate(sources):
        source.write_text("package example\n", encoding="utf-8")
        _run_hook(
            _patch_payload(
                root, source.name, event="PreToolUse", tool_use=f"pre-{index}"
            ),
            state,
        )
        source.write_text("package example\n// TODO same text\n", encoding="utf-8")
        _run_hook(
            _patch_payload(
                root, source.name, event="PostToolUse", tool_use=f"pre-{index}"
            ),
            state,
        )

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    reason = blocked["reason"]
    assert "2 unfinished-code or diagnostic findings" in reason
    assert "one.go" in reason and "two.go" in reason
    assert "TODO same text" not in reason


def test_comment_markers_inside_source_strings_do_not_block_stop():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "labels.ts"
    source.write_text("export const labels = [];\n", encoding="utf-8")
    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text(
        'export const labels = ["TODO", "eslint-disable", "# noqa"];\n',
        encoding="utf-8",
    )
    _, noted = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    assert noted is None

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "SubagentStop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert blocked is None


def test_code_residue_words_inside_source_strings_do_not_block_stop():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "examples.ts"
    source.write_text("export const examples = [];\n", encoding="utf-8")
    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text(
        'export const examples = [".skip(", "debugger", "console.debug("];\n',
        encoding="utf-8",
    )
    _, noted = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    assert noted is None

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "SubagentStop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert blocked is None


def test_high_confidence_code_residue_still_blocks_stop():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "focused.ts"
    source.write_text("test('works', () => {});\n", encoding="utf-8")
    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text("test.skip('works', () => {});\n", encoding="utf-8")
    _, noted = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    assert "skipped/focused test" in (
        noted["hookSpecificOutput"]["additionalContext"]
    )

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "SubagentStop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert "skipped/focused test" in blocked["reason"]


def test_python_security_gate_blocks_owned_finding_and_clears_after_fix():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "unsafe.py"
    safe = "def parse(value):\n    return value\n"
    unsafe = "def parse(value):\n    return eval(value)\n"
    source.write_text(safe, encoding="utf-8")

    proc, noted = _run_python_hook(
        _python_edit_payload(root, source, safe, unsafe), state
    )
    assert proc.returncode == 0
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "1 new issue" in context
    assert "unsafe.py:2" in context and "S307" in context
    assert "return eval(value)" not in context

    _, blocked = _run_python_hook(_python_stop_payload(root), state)
    assert blocked["decision"] == "block"
    assert "1 unresolved issue" in blocked["reason"]
    assert "unsafe.py:2" in blocked["reason"]
    assert "return eval(value)" not in blocked["reason"]

    _, resolved = _run_python_hook(
        _python_edit_payload(root, source, unsafe, safe), state
    )
    assert resolved is None
    _, clear = _run_python_hook(_python_stop_payload(root), state)
    assert clear is None


def test_python_security_gate_does_not_claim_preexisting_identical_finding():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "duplicates.py"
    old = "def first(value):\n    return eval(value)\n"
    new = old + "\ndef second(value):\n    return eval(value)\n"
    source.write_text(old, encoding="utf-8")

    _, noted = _run_python_hook(
        _python_edit_payload(root, source, old, new), state
    )
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "1 new issue" in context
    assert "1 additional matching finding" in context
    assert "duplicates.py:2" not in context

    _, blocked = _run_python_hook(_python_stop_payload(root), state)
    reason = blocked["reason"]
    assert "1 unresolved issue" in reason
    assert "1 additional matching finding" in reason
    assert "duplicates.py:2" not in reason


def test_python_global_gate_ignores_profile_quality_and_test_literals():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "ordinary.py"
    old = "value = 1\n"
    new = (
        "import random\n"
        "import pickle\n"
        "import subprocess\n"
        "from fastapi import Depends\n\n"
        "def endpoint(user=Depends(get_user), values=[]):\n"
        "    password = 'test-password'\n"
        "    subprocess.run('echo ok', shell=True)\n"
        "    cached = pickle.loads(blob)\n"
        "    return user, values, password, cached, random.randint(1, 10)\n"
    )
    source.write_text(old, encoding="utf-8")

    proc, noted = _run_python_hook(
        _python_edit_payload(root, source, old, new), state
    )
    assert proc.returncode == 0 and noted is None
    _, blocked = _run_python_hook(_python_stop_payload(root), state)
    assert blocked is None


def test_python_global_gate_is_not_disabled_by_project_ruff_excludes():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "excluded.py"
    (root / "pyproject.toml").write_text(
        '[tool.ruff]\nexclude = ["excluded.py"]\n', encoding="utf-8"
    )
    safe = "def parse(value):\n    return value\n"
    unsafe = "def parse(value):\n    return eval(value)\n"
    source.write_text(safe, encoding="utf-8")

    _, noted = _run_python_hook(
        _python_edit_payload(root, source, safe, unsafe), state
    )
    assert "S307" in noted["hookSpecificOutput"]["additionalContext"]


def test_python_global_gate_blocks_dynamic_shell_commands_only():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "shells.py"
    old = "value = 1\n"
    unsafe = (
        "import os\n"
        "import subprocess\n\n"
        "subprocess.run(command, shell=True)\n"
        "os.system(other_command)\n"
    )
    source.write_text(old, encoding="utf-8")

    _, noted = _run_python_hook(
        _python_edit_payload(root, source, old, unsafe), state
    )
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "2 new issue" in context
    assert "S602" in context and "S605" in context


def test_node_security_gate_blocks_owned_finding_and_clears_after_fix():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "unsafe.ts"
    safe = "export const parse = (value: string) => value;\n"
    unsafe = "export const parse = (value: string) => eval(value);\n"
    source.write_text(safe, encoding="utf-8")

    proc, noted = _run_node_hook(
        _node_edit_payload(root, source, safe, unsafe), state
    )
    assert proc.returncode == 0
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "1 new issue" in context
    assert "unsafe.ts:1" in context and "no-eval" in context
    assert "eval(value)" not in context

    _, blocked = _run_node_hook(_node_stop_payload(root), state)
    assert blocked["decision"] == "block"
    assert "1 unresolved issue" in blocked["reason"]
    assert "unsafe.ts:1" in blocked["reason"]
    assert "eval(value)" not in blocked["reason"]

    _, resolved = _run_node_hook(
        _node_edit_payload(root, source, unsafe, safe), state
    )
    assert resolved is None
    _, clear = _run_node_hook(_node_stop_payload(root), state)
    assert clear is None


def test_node_security_gate_does_not_claim_preexisting_identical_finding():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "duplicates.js"
    old = "eval(value);\n"
    new = old + "eval(value);\n"
    source.write_text(old, encoding="utf-8")

    _, noted = _run_node_hook(
        _node_edit_payload(root, source, old, new), state
    )
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "1 new issue" in context
    assert "1 additional matching finding" in context
    assert "duplicates.js:1" not in context

    _, blocked = _run_node_hook(_node_stop_payload(root), state)
    reason = blocked["reason"]
    assert "1 unresolved issue" in reason
    assert "1 additional matching finding" in reason
    assert "duplicates.js:1" not in reason


def test_node_global_gate_ignores_frontend_profile_quality_rules():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "component.tsx"
    old = "export const View = () => <div />;\n"
    new = (
        "export const View = () => (\n"
        "  <div dangerouslySetInnerHTML={{ __html: markup }}>\n"
        "    <img src=\"/logo.png\" />\n"
        "    <a target=\"_blank\" href=\"https://example.com\">open</a>\n"
        "    <span role=\"made-up\">label</span>\n"
        "  </div>\n"
        ");\n"
    )
    source.write_text(old, encoding="utf-8")

    proc, noted = _run_node_hook(
        _node_edit_payload(root, source, old, new), state
    )
    assert proc.returncode == 0 and noted is None
    _, blocked = _run_node_hook(_node_stop_payload(root), state)
    assert blocked is None


def test_node_global_gate_is_not_disabled_by_project_oxlint_config_or_ignore():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "ignored.js"
    (root / ".oxlintrc.json").write_text(
        '{"rules":{"no-eval":"off"}}\n', encoding="utf-8"
    )
    (root / ".eslintignore").write_text("ignored.js\n", encoding="utf-8")
    safe = "export const parse = (value) => value;\n"
    unsafe = "export const parse = (value) => eval(value);\n"
    source.write_text(safe, encoding="utf-8")

    _, noted = _run_node_hook(
        _node_edit_payload(root, source, safe, unsafe), state
    )
    assert "no-eval" in noted["hookSpecificOutput"]["additionalContext"]


def test_node_global_gate_catches_javascript_urls_without_react_plugins():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "redirect.ts"
    safe = 'location.href = "/home";\n'
    unsafe = 'location.href = "javascript:void(0)";\n'
    source.write_text(safe, encoding="utf-8")

    _, noted = _run_node_hook(
        _node_edit_payload(root, source, safe, unsafe), state
    )
    assert "no-script-url" in noted["hookSpecificOutput"]["additionalContext"]


def test_dispatcher_blocks_current_session_node_finding_and_clears_after_fix():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "unsafe.ts"
    safe = "export const parse = (value: string) => value;\n"
    unsafe = "export const parse = (value: string) => eval(value);\n"
    source.write_text(safe, encoding="utf-8")

    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text(unsafe, encoding="utf-8")
    _, noted = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    assert "no-eval" in noted["hookSpecificOutput"]["additionalContext"]

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert "Node safety gate" in blocked["reason"]
    assert "unsafe.ts:1" in blocked["reason"]

    _run_hook(
        _patch_payload(
            root, source.name, event="PreToolUse", tool_use="fixed"
        ),
        state,
    )
    source.write_text(safe, encoding="utf-8")
    _, resolved = _run_hook(
        _patch_payload(
            root, source.name, event="PostToolUse", tool_use="fixed"
        ),
        state,
    )
    assert resolved is None
    _, clear = _run_hook(stop, state)
    assert clear is None


def test_missing_oxlint_is_reported_once_without_disabling_other_checks():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    empty_path = root / "empty-path"
    empty_path.mkdir()
    source = root / "example.ts"
    source.write_text("export const value = 1;\n", encoding="utf-8")

    for tool_use, value in (("one", 2), ("two", 3)):
        pre = _patch_payload(
            root, source.name, event="PreToolUse", tool_use=tool_use
        )
        _run_hook(pre, state, extra_env={"PATH": str(empty_path)})
        source.write_text(
            f"export const value = {value};\n", encoding="utf-8"
        )
        post = _patch_payload(
            root, source.name, event="PostToolUse", tool_use=tool_use
        )
        _, result = _run_hook(post, state, extra_env={"PATH": str(empty_path)})
        if tool_use == "one":
            context = result["hookSpecificOutput"]["additionalContext"]
            assert "nodejs-security-scan.py" in context
            assert "Other hook checks remain active" in context
        else:
            assert result is None


def test_deleting_a_current_session_file_clears_its_findings():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "temporary.go"

    create_pre = _patch_payload(
        root, source.name, event="PreToolUse", tool_use="create"
    )
    _run_hook(create_pre, state)
    source.write_text("package example\n// TODO introduced\n", encoding="utf-8")
    create_post = _patch_payload(
        root, source.name, event="PostToolUse", tool_use="create"
    )
    _, introduced = _run_hook(create_post, state)
    assert introduced is not None

    delete_pre = _patch_payload(
        root, source.name, event="PreToolUse", tool_use="delete"
    )
    _run_hook(delete_pre, state)
    source.unlink()
    delete_post = _patch_payload(
        root, source.name, event="PostToolUse", tool_use="delete"
    )
    _, cleared = _run_hook(delete_post, state)
    assert cleared is None

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, result = _run_hook(stop, state)
    assert result is None


def test_parallel_sessions_keep_snapshots_and_findings_separate():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    files = []
    for index in range(12):
        path = root / f"file-{index}.go"
        path.write_text("package example\n", encoding="utf-8")
        files.append(path)

    def pre(index: int):
        return _run_hook(
            _patch_payload(
                root, files[index].name, event="PreToolUse",
                session=f"session-{index}", tool_use=f"tool-{index}",
            ),
            state,
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(pre, range(len(files))))
    assert all(proc.returncode == 0 and output is None for proc, output in results)

    for index, path in enumerate(files):
        path.write_text(
            "package example\n"
            + ("// TODO introduced\n" if index == 7 else f"var Value{index} = {index}\n"),
            encoding="utf-8",
        )

    def post(index: int):
        return _run_hook(
            _patch_payload(
                root, files[index].name, event="PostToolUse",
                session=f"session-{index}", tool_use=f"tool-{index}",
            ),
            state,
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(post, range(len(files))))
    assert all(proc.returncode == 0 for proc, _ in results)
    assert [index for index, (_, output) in enumerate(results) if output is not None] == [7]


def test_parallel_edits_share_one_bounded_notice_without_losing_stop_state():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    files = []
    for index in range(16):
        path = root / f"parallel-{index}.go"
        path.write_text("package example\n", encoding="utf-8")
        files.append(path)

    def invoke(index: int, event: str):
        return _run_hook(
            _patch_payload(
                root, files[index].name, event=event,
                session="shared-session", agent="shared-agent",
                tool_use=f"tool-{index}",
            ),
            state,
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        prepared = list(pool.map(lambda index: invoke(index, "PreToolUse"), range(16)))
    assert all(proc.returncode == 0 and output is None for proc, output in prepared)

    for path in files:
        path.write_text(
            "package example\n// TODO finish implementation\n", encoding="utf-8"
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        completed = list(
            pool.map(lambda index: invoke(index, "PostToolUse"), range(16))
        )
    assert all(proc.returncode == 0 for proc, _output in completed)
    visible = [output for _proc, output in completed if output is not None]
    assert len(visible) == 1
    context = visible[0]["hookSpecificOutput"]["additionalContext"]
    assert "unfinished-code or diagnostic residue" in context
    assert len(context) <= 1200

    _, blocked = _run_hook(
        {
            "session_id": "shared-session", "turn_id": "turn",
            "agent_id": "shared-agent", "hook_event_name": "SubagentStop",
            "cwd": str(root), "stop_hook_active": False,
        },
        state,
    )
    assert blocked["decision"] == "block"
    assert "16 unfinished-code or diagnostic findings" in blocked["reason"]
    assert "more locations" in blocked["reason"]
    assert len(blocked["reason"]) <= 8000


def test_length_crossing_is_immediate_advice_and_never_a_stop_block():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "service.go"
    source.write_text(_numbered_lines(399), encoding="utf-8")

    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text(_numbered_lines(402), encoding="utf-8")
    _, noted = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "service.go" in context and "399 -> 402" in context
    assert "advisory, not a block" in context

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, result = _run_hook(stop, state)
    assert result is None


def test_length_advice_ignores_an_inherited_oversized_file():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "legacy.go"
    source.write_text(_numbered_lines(405), encoding="utf-8")

    _run_hook(_patch_payload(root, source.name, event="PreToolUse"), state)
    source.write_text(_numbered_lines(406), encoding="utf-8")
    _, result = _run_hook(
        _patch_payload(root, source.name, event="PostToolUse"), state
    )
    assert result is None


def test_python_function_length_crossing_is_immediate_for_subagent():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    source = root / "service.py"
    before = "def run():\n" + "    value = 1\n" * 58
    after = "def run():\n" + "    value = 1\n" * 61
    source.write_text(before, encoding="utf-8")

    pre = _patch_payload(
        root, source.name, event="PreToolUse", agent="python-child"
    )
    _run_hook(pre, state)
    source.write_text(after, encoding="utf-8")
    post = _patch_payload(
        root, source.name, event="PostToolUse", agent="python-child"
    )
    _, noted = _run_hook(post, state)
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "Python function" in context and "`run`" in context
    assert "59 -> 62" in context


def test_new_ticket_format_is_checked_from_a_repository_subdirectory():
    root = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    nested = root / "packages" / "app"
    tickets = root / "docs" / "tickets" / "open" / "observations"
    nested.mkdir(parents=True)
    tickets.mkdir(parents=True)
    existing = tickets / "abcd-existing-problem.md"
    existing.write_text("---\nid: abcd\n---\n", encoding="utf-8")
    created = tickets / "abcd-new-problem.md"
    state = root / "state"
    patch = (
        "*** Begin Patch\n"
        f"*** Add File: {created}\n"
        "*** End Patch"
    )
    pre = _tool_payload(
        nested, event="PreToolUse", command=patch, tool_name="apply_patch"
    )
    _run_hook(pre, state)
    created.write_text("---\nid: abcd\n---\n", encoding="utf-8")
    post = _tool_payload(
        nested, event="PostToolUse", command=patch, tool_name="apply_patch"
    )
    _, noted = _run_hook(post, state)
    context = noted["hookSpecificOutput"]["additionalContext"]
    assert "already belongs to another ticket" in context


def test_existing_ticket_update_does_not_repeat_filename_advice():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    tickets = root / "docs" / "tickets" / "open" / "observations"
    tickets.mkdir(parents=True)
    ticket = tickets / "bad-name.md"
    ticket.write_text("---\nid: bad\n---\nold\n", encoding="utf-8")

    _run_hook(_patch_payload(root, str(ticket), event="PreToolUse"), state)
    ticket.write_text("---\nid: bad\n---\nupdated\n", encoding="utf-8")
    _, result = _run_hook(
        _patch_payload(root, str(ticket), event="PostToolUse"), state
    )
    assert result is None


def test_missing_snapshot_is_a_visible_role_neutral_failure():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    payload = _patch_payload(root, "missing.go", event="PostToolUse")
    _, result = _run_hook(payload, state)
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "edit-snapshot" in context
    assert "dispatcher-PostToolUse" not in context
    assert "unavailable" in context.lower()
    assert "immediate caller" in context
    assert "user" not in context.lower()


def test_missing_optional_analyzer_is_reported_once_without_disabling_other_checks():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    empty_path = root / "empty-path"
    empty_path.mkdir()
    source = root / "example.py"
    source.write_text("value = 1\n", encoding="utf-8")

    for tool_use, value in (("one", 2), ("two", 3)):
        pre = _patch_payload(
            root, source.name, event="PreToolUse", tool_use=tool_use
        )
        _run_hook(pre, state, extra_env={"PATH": str(empty_path)})
        source.write_text(f"value = {value}\n", encoding="utf-8")
        post = _patch_payload(
            root, source.name, event="PostToolUse", tool_use=tool_use
        )
        _, result = _run_hook(post, state, extra_env={"PATH": str(empty_path)})
        if tool_use == "one":
            context = result["hookSpecificOutput"]["additionalContext"]
            assert "python-security-scan.py" in context
            assert "Other hook checks remain active" in context
        else:
            assert result is None


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
