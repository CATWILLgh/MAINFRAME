#!/usr/bin/env python3
"""Focused contracts for the opt-in Codex-to-Pi completion bridge."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "adapters" / "codex" / "hooks" / "scripts" / "_pi_wait.py"
SPEC = importlib.util.spec_from_file_location("mainframe_pi_wait_test", MODULE_PATH)
assert SPEC and SPEC.loader
PI_WAIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PI_WAIT)


def _payload(project: Path, session: str = "session-one") -> dict:
    return {
        "session_id": session,
        "turn_id": "turn-one",
        "tool_use_id": "tool-one",
        "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {
            "command": "mainframe-pi engineer --mode new --request .agents/runtime/pi/requests/a.json"
        },
    }


def _enable(home: Path, *, wait: int = 2, grace: int = 1) -> None:
    target = home / ".codex" / "mainframe" / "pi-wait-enabled.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "waitTimeoutSeconds": wait,
                "startupGraceSeconds": grace,
            }
        ),
        encoding="utf-8",
    )


def _write_state(project: Path, value: dict) -> Path:
    target = project / ".agents" / "runtime" / "pi" / "engineer" / "worktree" / "latest-run.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"schemaVersion": 1, **value}), encoding="utf-8")
    return target


def test_disabled_bridge_is_silent() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        payload = _payload(project)
        PI_WAIT.register(payload)
        assert PI_WAIT.wait_for_completion(payload) is None
        assert not (home / ".codex" / "mainframe" / "pi-waits").exists()
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_terminal_run_resumes_once_and_consumes_registration() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home)
        payload = _payload(project)
        PI_WAIT.register(payload)
        result = project / ".agents" / "runtime" / "pi" / "engineer" / "worktree" / "runs" / "new" / "result.json"
        result.parent.mkdir(parents=True)
        result.write_text("{}\n", encoding="utf-8")
        _write_state(
            project,
            {
                "runId": "new-run",
                "startedAt": "2026-08-21T10:00:00Z",
                "phase": "finished",
                "status": "ready-for-architect-review",
                "resultPath": str(result.relative_to(project)),
                "pid": 999999,
            },
        )
        reason = PI_WAIT.wait_for_completion(payload)
        assert reason and "ready-for-architect-review" in reason
        assert str(result.resolve()) in reason
        assert PI_WAIT.wait_for_completion(payload) is None
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_existing_run_is_not_mistaken_for_new_work() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home)
        state = _write_state(
            project,
            {
                "runId": "old-run",
                "startedAt": "2026-08-21T09:00:00Z",
                "phase": "finished",
                "status": "ready-for-architect-review",
                "resultPath": ".agents/old-result.json",
                "pid": 999999,
            },
        )
        payload = _payload(project)
        PI_WAIT.register(payload)
        state.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": "new-run",
                    "startedAt": "2026-08-21T10:00:00Z",
                    "phase": "finished",
                    "status": "blocked",
                    "resultPath": ".agents/new-result.json",
                    "pid": 999999,
                }
            ),
            encoding="utf-8",
        )
        reason = PI_WAIT.wait_for_completion(payload)
        assert reason and "status `blocked`" in reason
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_failed_launch_is_consumed_at_post_tool_use_without_a_stop_warning() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home)
        payload = _payload(project, "failed-launch")
        PI_WAIT.register(payload)
        reason = PI_WAIT.complete_launch(payload)
        assert reason and "command's own output" in reason
        assert PI_WAIT.wait_for_completion(payload) is None
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_post_tool_use_keeps_registration_after_run_state_exists() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home)
        payload = _payload(project, "started-launch")
        PI_WAIT.register(payload)
        _write_state(
            project,
            {
                "runId": "started-run",
                "startedAt": "2026-08-22T10:00:00Z",
                "phase": "finished",
                "status": "blocked",
                "resultPath": ".agents/result.json",
                "pid": 999999,
            },
        )
        assert PI_WAIT.complete_launch(payload) is None
        reason = PI_WAIT.wait_for_completion(payload)
        assert reason and "status `blocked`" in reason
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_compound_or_subagent_commands_do_not_register() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home)
        compound = _payload(project, "compound")
        compound["tool_input"]["command"] += " &"
        PI_WAIT.register(compound)
        subagent = _payload(project, "subagent")
        subagent["agent_id"] = "worker"
        PI_WAIT.register(subagent)
        waits = home / ".codex" / "mainframe" / "pi-waits"
        assert not waits.exists()
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous


def test_stop_waits_for_a_running_worker_without_model_polling() -> None:
    home = Path(tempfile.mkdtemp())
    project = Path(tempfile.mkdtemp())
    previous = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(home / ".codex")
    try:
        _enable(home, wait=3, grace=1)
        payload = _payload(project, "delayed")
        PI_WAIT.register(payload)
        state = _write_state(
            project,
            {
                "runId": "delayed-run",
                "startedAt": "2026-08-21T10:00:00Z",
                "phase": "running",
                "status": "running",
                "resultPath": None,
                "pid": os.getpid(),
            },
        )

        def finish() -> None:
            time.sleep(0.05)
            state.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "runId": "delayed-run",
                        "startedAt": "2026-08-21T10:00:00Z",
                        "phase": "finished",
                        "status": "incomplete",
                        "resultPath": ".agents/delayed-result.json",
                        "pid": os.getpid(),
                    }
                ),
                encoding="utf-8",
            )

        worker = threading.Thread(target=finish)
        worker.start()
        reason = PI_WAIT.wait_for_completion(payload)
        worker.join()
        assert reason and "status `incomplete`" in reason
    finally:
        if previous is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = previous
