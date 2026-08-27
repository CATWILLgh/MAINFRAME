#!/usr/bin/env python3
"""Behavior tests for the optional cross-adapter peer session launchers."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
CLAUDE_LAUNCHER = ROOT / "adapters" / "codex" / "optional" / "bin" / "mainframe-claude"
CODEX_LAUNCHER = ROOT / "adapters" / "claude-code" / "optional" / "bin" / "mainframe-codex"
PEER_WAIT = ROOT / "adapters" / "codex" / "hooks" / "scripts" / "_peer_wait.py"


def _executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _wait_for_state(root: Path, *, status: str = "completed") -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        paths = list(root.glob("*/state.json"))
        if paths:
            value = json.loads(paths[0].read_text(encoding="utf-8"))
            if value.get("status") == status:
                return value
            if value.get("status") == "failed":
                raise AssertionError(value)
        time.sleep(0.05)
    raise AssertionError("peer worker did not publish terminal state")


def test_claude_launcher_keeps_customizations_and_resumes_exact_session():
    root = Path(tempfile.mkdtemp())
    project = root / "project"
    project.mkdir()
    request = root / "request.md"
    request.write_text("Review one result.\n", encoding="utf-8")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    log = root / "claude-invocations.jsonl"
    _executable(
        fake_bin / "claude",
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['PEER_TEST_LOG'], 'a') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "sys.stdin.read()\n"
        "print(json.dumps({'session_id':'claude-session-1','result':'checked','subtype':'success','is_error':False}))\n",
    )
    env = dict(
        os.environ,
        CODEX_HOME=str(root / "codex-home"),
        PATH=f"{fake_bin}:{os.environ['PATH']}",
        PEER_TEST_LOG=str(log),
    )
    first = subprocess.run(
        [
            sys.executable, str(CLAUDE_LAUNCHER), "new",
            "--role", "review", "--project", str(project),
            "--request", str(request), "--model", "haiku",
        ],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert first.returncode == 0, first.stderr
    runs = root / "codex-home" / "mainframe" / "peer-runs" / "claude"
    project_runs = next(runs.iterdir())
    state = _wait_for_state(project_runs)
    assert state["sessionId"] == "claude-session-1"
    first_args = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "--safe-mode" not in first_args
    assert "--effort" not in first_args
    assert first_args[first_args.index("--permission-mode") + 1] == "dontAsk"

    follow_up = root / "follow-up.md"
    follow_up.write_text("Check the correction.\n", encoding="utf-8")
    second = subprocess.run(
        [
            sys.executable, str(CLAUDE_LAUNCHER), "resume",
            "--session", "claude-session-1", "--project", str(project),
            "--request", str(follow_up),
        ],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert second.returncode == 0, second.stderr
    deadline = time.monotonic() + 10
    while len(log.read_text(encoding="utf-8").splitlines()) < 2:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    second_args = json.loads(log.read_text(encoding="utf-8").splitlines()[1])
    assert second_args[second_args.index("--resume") + 1] == "claude-session-1"


def test_claude_launcher_refuses_an_ambiguous_concurrent_peer():
    root = Path(tempfile.mkdtemp())
    project = root / "project"
    project.mkdir()
    request = root / "request.md"
    request.write_text("Review.\n", encoding="utf-8")
    codex_home = root / "codex-home"
    key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:24]
    state_dir = codex_home / "mainframe" / "peer-runs" / "claude" / key / "active"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text(json.dumps({
        "schemaVersion": 1,
        "runId": "active",
        "role": "review",
        "phase": "running",
        "pid": os.getpid(),
    }), encoding="utf-8")
    env = dict(os.environ, CODEX_HOME=str(codex_home))
    result = subprocess.run(
        [
            sys.executable, str(CLAUDE_LAUNCHER), "new",
            "--role", "review", "--project", str(project),
            "--request", str(request), "--model", "opus", "--effort", "medium",
        ],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert result.returncode == 2
    assert "another Claude peer is active" in result.stderr


def test_codex_launcher_preserves_role_model_and_exact_session():
    root = Path(tempfile.mkdtemp())
    project = root / "project"
    project.mkdir()
    request = root / "request.md"
    request.write_text("Implement one result.\n", encoding="utf-8")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    log = root / "codex-invocations.jsonl"
    _executable(
        fake_bin / "codex",
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "args=sys.argv[1:]\n"
        "with open(os.environ['PEER_TEST_LOG'], 'a') as f:\n"
        "    f.write(json.dumps(args) + '\\n')\n"
        "sys.stdin.read()\n"
        "out=pathlib.Path(args[args.index('-o')+1]); out.write_text('implemented\\n')\n"
        "print(json.dumps({'type':'thread.started','thread_id':'codex-session-1'}))\n",
    )
    env = dict(
        os.environ,
        CLAUDE_CONFIG_DIR=str(root / "claude-home"),
        PATH=f"{fake_bin}:{os.environ['PATH']}",
        PEER_TEST_LOG=str(log),
    )
    first = subprocess.run(
        [
            sys.executable, str(CODEX_LAUNCHER), "new",
            "--role", "implement", "--project", str(project),
            "--request", str(request), "--model", "gpt-5.6-terra",
            "--effort", "medium",
        ],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert first.returncode == 0, first.stderr
    assert "peer_session_id=codex-session-1" in first.stdout
    first_args = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "--approve-for-me" in first_args
    assert "--ignore-user-config" not in first_args

    follow_up = root / "follow-up.md"
    follow_up.write_text("Finish the same result.\n", encoding="utf-8")
    second = subprocess.run(
        [
            sys.executable, str(CODEX_LAUNCHER), "resume",
            "--session", "codex-session-1", "--project", str(project),
            "--request", str(follow_up),
        ],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert second.returncode == 0, second.stderr
    second_args = json.loads(log.read_text(encoding="utf-8").splitlines()[1])
    resume = second_args.index("resume")
    assert second_args[resume + 2] == "codex-session-1"
    assert "gpt-5.6-terra" in second_args
    assert 'model_reasoning_effort="medium"' in second_args


def test_codex_wait_bridge_creates_one_result_continuation_without_polling():
    root = Path(tempfile.mkdtemp())
    codex_home = root / "codex-home"
    project = root / "project"
    project.mkdir()
    marker = codex_home / "mainframe" / "peer-work-enabled.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "schemaVersion": 1,
        "waitTimeoutSeconds": 5,
        "startupGraceSeconds": 1,
    }), encoding="utf-8")
    old_home = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(codex_home)
    try:
        spec = importlib.util.spec_from_file_location("peer_wait_test", PEER_WAIT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = {
            "session_id": "root-session",
            "turn_id": "turn-1",
            "tool_use_id": "tool-1",
            "cwd": str(project),
            "tool_input": {
                "command": "mainframe-claude new --role review --project /tmp/p --request /tmp/r --model opus --effort medium"
            },
        }
        module.register(payload)
        key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:24]
        run_dir = codex_home / "mainframe" / "peer-runs" / "claude" / key / "run-one"
        run_dir.mkdir(parents=True)
        result = run_dir / "result.json"
        result.write_text(json.dumps({"result": "independent result"}), encoding="utf-8")
        state = {
            "schemaVersion": 1,
            "runId": "run-one",
            "role": "review",
            "sessionId": "claude-session-1",
            "phase": "finished",
            "status": "completed",
            "startedAt": "2026-08-27T00:00:00+00:00",
            "resultPath": str(result),
        }
        (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        continuation = module.wait_for_completion(payload)
        assert continuation is not None
        assert "claude-session-1" in continuation
        assert "independent result" in continuation
        assert module.wait_for_completion(payload) is None
    finally:
        if old_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = old_home


def _run_all() -> None:
    failures = 0
    tests = [
        (name, fn) for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
