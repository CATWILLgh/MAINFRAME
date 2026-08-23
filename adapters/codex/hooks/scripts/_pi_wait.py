#!/usr/bin/env python3
"""Session-scoped bridge from a background Pi engineer run to Codex Stop."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import time


TERMINAL_STATUSES = {
    "ready-for-architect-review",
    "blocked",
    "plan-conflict",
    "incomplete",
    "failed",
}


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser().resolve()


def _config_path() -> Path:
    return _codex_home() / "mainframe" / "pi-wait-enabled.json"


def enabled() -> bool:
    return _config_path().is_file()


def _config() -> dict:
    value = json.loads(_config_path().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ValueError("Pi wait configuration is invalid")
    wait = value.get("waitTimeoutSeconds")
    grace = value.get("startupGraceSeconds")
    if not isinstance(wait, int) or not 1 <= wait <= 86_400:
        raise ValueError("Pi wait timeout is invalid")
    if not isinstance(grace, int) or not 1 <= grace <= 60:
        raise ValueError("Pi wait startup grace is invalid")
    return value


def _session_key(payload: dict) -> str | None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return hashlib.sha256(session_id.encode()).hexdigest()[:24]


def _registration_path(payload: dict) -> Path | None:
    key = _session_key(payload)
    if key is None:
        return None
    return _codex_home() / "mainframe" / "pi-waits" / f"{key}.json"


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _is_engineer_command(command: object) -> bool:
    if not isinstance(command, str) or not command.strip():
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if any(token in {";", "&&", "||", "|", "&"} for token in tokens):
        return False
    for index, token in enumerate(tokens[:-1]):
        if Path(token).name == "mainframe-pi" and tokens[index + 1] == "engineer":
            return True
    return False


def _latest_states(project_root: Path) -> list[dict]:
    states: list[dict] = []
    base = project_root / ".agents" / "runtime" / "pi" / "engineer"
    for candidate in base.glob("*/latest-run.json"):
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("schemaVersion") != 1:
            continue
        value["_statePath"] = str(candidate)
        states.append(value)
    return states


def register(payload: dict) -> None:
    if not enabled() or payload.get("agent_id"):
        return
    command = (payload.get("tool_input") or {}).get("command")
    if not _is_engineer_command(command):
        return
    registration = _registration_path(payload)
    if registration is None:
        return
    project_root = Path(payload.get("cwd") or os.getcwd()).resolve()
    prior_ids = sorted(
        state["runId"]
        for state in _latest_states(project_root)
        if isinstance(state.get("runId"), str)
    )
    _atomic_write(
        registration,
        {
            "schemaVersion": 1,
            "projectRoot": str(project_root),
            "turnId": str(payload.get("turn_id") or ""),
            "toolUseId": str(payload.get("tool_use_id") or ""),
            "registeredAt": datetime.now(timezone.utc).isoformat(),
            "priorRunIds": prior_ids,
        },
    )


def _read_registration(payload: dict) -> tuple[Path, dict] | None:
    path = _registration_path(payload)
    if path is None or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ValueError("Pi wait registration is invalid")
    project = value.get("projectRoot")
    prior = value.get("priorRunIds")
    if not isinstance(project, str) or not Path(project).is_absolute():
        raise ValueError("Pi wait project root is invalid")
    if not isinstance(prior, list) or not all(isinstance(item, str) for item in prior):
        raise ValueError("Pi wait prior run identifiers are invalid")
    return path, value


def _newest_run(registration: dict) -> dict | None:
    project_root = Path(registration["projectRoot"]).resolve()
    prior = set(registration["priorRunIds"])
    candidates = [
        state for state in _latest_states(project_root)
        if isinstance(state.get("runId"), str) and state["runId"] not in prior
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda state: str(state.get("startedAt") or ""))


def complete_launch(payload: dict) -> str | None:
    """Consume a foreground launch that ended before Pi created run state."""
    if not enabled() or payload.get("agent_id") or payload.get("tool_name") != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command")
    if not _is_engineer_command(command):
        return None
    pending = _read_registration(payload)
    if pending is None:
        return None
    registration_path, registration = pending
    registered_tool_use = registration.get("toolUseId")
    current_tool_use = payload.get("tool_use_id")
    if (
        isinstance(registered_tool_use, str)
        and registered_tool_use
        and registered_tool_use != current_tool_use
    ):
        return None
    if _newest_run(registration) is not None:
        return None
    registration_path.unlink(missing_ok=True)
    return (
        "The MAINFRAME Pi engineer command ended before creating run state. "
        "Treat the command's own output above as the terminal launch result; "
        "do not wait for or repeat this launch."
    )


def _pid_alive(raw: object) -> bool:
    if not isinstance(raw, int) or raw <= 0:
        return False
    try:
        os.kill(raw, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _safe_result_path(registration: dict, state: dict) -> Path:
    project_root = Path(registration["projectRoot"]).resolve()
    raw = state.get("resultPath")
    if not isinstance(raw, str) or not raw or "\n" in raw or "\r" in raw:
        return Path(state["_statePath"])
    candidate = (project_root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError:
        return Path(state["_statePath"])
    return candidate


def wait_for_completion(payload: dict) -> str | None:
    if not enabled() or payload.get("agent_id"):
        return None
    pending = _read_registration(payload)
    if pending is None:
        return None
    registration_path, registration = pending
    config = _config()
    deadline = time.monotonic() + config["waitTimeoutSeconds"]
    startup_deadline = time.monotonic() + config["startupGraceSeconds"]
    while True:
        state = _newest_run(registration)
        if state is not None:
            status = state.get("status")
            phase = state.get("phase")
            if phase == "finished" and status in TERMINAL_STATUSES:
                registration_path.unlink(missing_ok=True)
                result_path = _safe_result_path(registration, state)
                return (
                    f"MAINFRAME Pi engineer finished with status `{status}`. "
                    f"Read `{result_path}`, inspect the actual diff and checks, and continue "
                    "the primary architect review. Pi's internal verifier is not final acceptance."
                )
            if phase == "running" and not _pid_alive(state.get("pid")):
                registration_path.unlink(missing_ok=True)
                return (
                    "MAINFRAME Pi engineer stopped without writing a terminal result. "
                    f"Inspect `{state.get('_statePath')}` and the background command output, "
                    "then report or correct the failed run."
                )
        elif time.monotonic() >= startup_deadline:
            registration_path.unlink(missing_ok=True)
            return (
                "MAINFRAME Pi engineer did not create its run-state file after launch. "
                "Inspect the background command output before treating the delegated block as started."
            )
        if time.monotonic() >= deadline:
            registration_path.unlink(missing_ok=True)
            return (
                "MAINFRAME Pi engineer is still running after the configured wait window. "
                "Inspect its run state and continue without starting a duplicate writer."
            )
        time.sleep(1)
