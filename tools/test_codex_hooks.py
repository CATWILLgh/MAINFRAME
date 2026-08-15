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
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "adapters" / "codex"
HOOK = ADAPTER / "hooks" / "scripts" / "mainframe-hook.py"
HOOKS_SOURCE = ADAPTER / "hooks" / "hooks.json"
MANAGER = ADAPTER / "scripts" / "manage-hooks.py"


def _state_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "MAINFRAME_CODEX_SNAPSHOT_DIR": str(root / "snapshots"),
        "MAINFRAME_MARKER_STATE_DIR": str(root / "markers"),
        "MAINFRAME_LENGTH_STATE_DIR": str(root / "length"),
        "MAINFRAME_FALLOW_STATE_DIR": str(root / "fallow"),
        "MAINFRAME_NOTICE_STATE_DIR": str(root / "notices"),
    })
    return env


def _run_hook(
    payload: dict, state: Path, *, extra_env: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess, dict | None]:
    env = _state_env(state)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env=env,
    )
    output = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc, output


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


def test_hook_source_is_one_handler_per_event_and_has_bounded_outputs():
    source = json.loads(HOOKS_SOURCE.read_text(encoding="utf-8"))
    assert set(source["hooks"]) == {
        "SessionStart", "PreToolUse", "PostToolUse", "Stop", "SubagentStop"
    }
    for event, groups in source["hooks"].items():
        assert len(groups) == 1
        assert len(groups[0]["hooks"]) == 1
        handler = groups[0]["hooks"][0]
        assert handler["type"] == "command"
        assert "mainframe-hook.py" not in handler["command"]
        assert "@MAINFRAME_HOOK_SCRIPT@" in handler["command"]
        assert 0 < handler["timeout"] <= 210
        if "additionalContextLimit" in handler:
            assert 0 < handler["additionalContextLimit"] <= 1600
        else:
            assert event in {"Stop", "SubagentStop"}
        assert "async" not in handler
    assert source["hooks"]["SessionStart"][0]["matcher"] == (
        "^(startup|resume|clear|compact)$"
    )


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
    module._load_module = lambda filename: (
        (_ for _ in ()).throw(ImportError("probe"))
        if filename == module.HEALTH_MODULES[0]
        else original_load(filename)
    )
    output = io.StringIO()
    with redirect_stdout(output):
        module._health({})
    failure = json.loads(output.getvalue())
    assert module.HEALTH_MODULES[0] in failure["systemMessage"]
    assert module.HEALTH_MODULES[0] in (
        failure["hookSpecificOutput"]["additionalContext"]
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


def test_command_safety_uses_rules_for_simple_forms_and_denies_bypasses():
    root = Path(tempfile.mkdtemp())
    state = root / "state"

    _, ordinary_delete = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm one-file.txt"), state
    )
    assert ordinary_delete is None

    _, reviewed_recursive = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -rf generated"), state
    )
    assert reviewed_recursive is None

    _, ambiguous_recursive = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -f -r generated"), state
    )
    assert ambiguous_recursive["hookSpecificOutput"]["permissionDecision"] == "deny"

    _, broad_recursive = _run_hook(
        _tool_payload(root, event="PreToolUse", command="rm -rf /"), state
    )
    assert broad_recursive["hookSpecificOutput"]["permissionDecision"] == "deny"

    _, normal_push = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git push"), state
    )
    assert normal_push is None

    _, rule_branch = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git branch -d old"), state
    )
    assert rule_branch is None

    _, positional_branch = _run_hook(
        _tool_payload(root, event="PreToolUse", command="git branch new"), state
    )
    assert positional_branch["hookSpecificOutput"]["permissionDecision"] == "deny"

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
    assert "temporary plan, phase, step" in context
    assert len(context) < 4000

    stop = {
        "session_id": "session", "turn_id": "turn", "agent_id": "",
        "hook_event_name": "Stop", "cwd": str(root),
        "stop_hook_active": False,
    }
    _, blocked = _run_hook(stop, state)
    assert blocked["decision"] == "block"
    assert "TODO/FIXME/HACK/XXX" in blocked["reason"]

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


def test_missing_snapshot_is_a_visible_role_neutral_failure():
    root = Path(tempfile.mkdtemp())
    state = root / "state"
    payload = _patch_payload(root, "missing.go", event="PostToolUse")
    _, result = _run_hook(payload, state)
    context = result["hookSpecificOutput"]["additionalContext"]
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
