#!/usr/bin/env python3
"""Process lifecycle and timeout contracts for the Antigravity hook bridge."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MAX_PROCESS_OUTPUT_BYTES = 262_144
PROCESS_POLL_SECONDS = 0.01
PROCESS_CLEANUP_BUDGET_SECONDS = 2
BRIDGE_OVERHEAD_SECONDS = 5
HANDLER_MARGIN_SECONDS = 5
MEMORY_LOADER_TIMEOUT_SECONDS = 15

PRE_DETECTORS = (
    "path-validation.py",
    "secret-commit-gate.py",
    "bash-pattern-reminder.py",
    "commit-conventional-reminder.py",
)
POST_DETECTORS = (
    "scan-suppression-markers.py",
    "comment-discipline-reminder.py",
    "ticket-id-format-reminder.py",
    "python-security-scan.py",
    "python-deps-audit.py",
    "nodejs-deps-audit.py",
    "nodejs-security-scan.py",
)
STOP_DETECTORS = (
    "stop-gate-suppression-markers.py",
    "stop-gate-comment-discipline.py",
    "python-security-stop-gate.py",
    "nodejs-security-stop-gate.py",
    "frontend-fsd-gate.py",
)

DETECTOR_TIMEOUT_SECONDS = {
    "path-validation.py": 10,
    "secret-commit-gate.py": 10,
    "bash-pattern-reminder.py": 2,
    "commit-conventional-reminder.py": 2,
    "scan-suppression-markers.py": 10,
    "comment-discipline-reminder.py": 10,
    "ticket-id-format-reminder.py": 5,
    "python-security-scan.py": 35,
    "python-deps-audit.py": 65,
    "nodejs-deps-audit.py": 65,
    "nodejs-security-scan.py": 40,
    "stop-gate-suppression-markers.py": 10,
    "stop-gate-comment-discipline.py": 60,
    "python-security-stop-gate.py": 60,
    "nodejs-security-stop-gate.py": 150,
    "frontend-fsd-gate.py": 125,
    "memory-reminder.py": 2,
}
EVENT_DETECTORS = {
    "PreToolUse": PRE_DETECTORS,
    "PostToolUse": POST_DETECTORS,
    "PreInvocation": (),
    "PostInvocation": (),
    "Stop": STOP_DETECTORS,
}
EVENT_BUDGET_SECONDS = {
    "PreToolUse": max(DETECTOR_TIMEOUT_SECONDS[name] for name in PRE_DETECTORS)
    + BRIDGE_OVERHEAD_SECONDS,
    "PostToolUse": max(DETECTOR_TIMEOUT_SECONDS[name] for name in POST_DETECTORS)
    + BRIDGE_OVERHEAD_SECONDS,
    "PreInvocation": MEMORY_LOADER_TIMEOUT_SECONDS + BRIDGE_OVERHEAD_SECONDS,
    "PostInvocation": BRIDGE_OVERHEAD_SECONDS,
    "Stop": max(DETECTOR_TIMEOUT_SECONDS[name] for name in STOP_DETECTORS)
    + DETECTOR_TIMEOUT_SECONDS["memory-reminder.py"]
    + BRIDGE_OVERHEAD_SECONDS,
}
HANDLER_TIMEOUT_SECONDS = {
    event: budget + HANDLER_MARGIN_SECONDS
    for event, budget in EVENT_BUDGET_SECONDS.items()
}


@dataclass
class _RunningProcess:
    index: int
    process: subprocess.Popen[bytes]
    deadline: float
    output: bytearray
    reader_done: threading.Event
    oversized: bool = False
    terminated: bool = False


def event_deadline(event: str) -> float:
    return time.monotonic() + EVENT_BUDGET_SECONDS[event]


def remaining_timeout(deadline: float, allowance: float) -> float:
    return min(allowance, max(0.0, deadline - time.monotonic()))


def _spawn(
    index: int,
    command: Sequence[str],
    input_bytes: bytes,
    deadline: float,
) -> _RunningProcess | None:
    input_file = tempfile.TemporaryFile()
    try:
        input_file.write(input_bytes)
        input_file.seek(0)
        kwargs = {"start_new_session": True} if os.name == "posix" else {}
        process = subprocess.Popen(
            command,
            stdin=input_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except (OSError, ValueError):
        input_file.close()
        return None
    input_file.close()
    stdout = process.stdout
    if stdout is None:
        _terminate(process)
        return None
    task = _RunningProcess(index, process, deadline, bytearray(), threading.Event())
    try:
        threading.Thread(
            target=_read_output,
            args=(task,),
            name=f"mainframe-detector-{index}",
            daemon=True,
        ).start()
    except RuntimeError:
        _terminate(process)
        stdout.close()
        return None
    return task


def _terminate(process: subprocess.Popen[bytes]) -> None:
    cleanup_deadline = time.monotonic() + PROCESS_CLEANUP_BUDGET_SECONDS
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
        except (OSError, subprocess.TimeoutExpired):
            pass


def _read_output(task: _RunningProcess) -> None:
    stdout = task.process.stdout
    if stdout is None:
        task.reader_done.set()
        return
    try:
        while not task.oversized:
            chunk = stdout.read(65_536)
            if not chunk:
                break
            remaining = MAX_PROCESS_OUTPUT_BYTES + 1 - len(task.output)
            task.output.extend(chunk[:remaining])
            task.oversized = len(task.output) > MAX_PROCESS_OUTPUT_BYTES
    except (OSError, ValueError):
        pass
    finally:
        try:
            stdout.close()
        except OSError:
            pass
        task.reader_done.set()


def _parse_output(task: _RunningProcess) -> dict | None:
    if (
        task.process.returncode
        or task.oversized
        or task.terminated
        or not task.reader_done.is_set()
    ):
        return None
    raw = bytes(task.output)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _collect(tasks: list[_RunningProcess], size: int) -> list[dict | None]:
    results: list[dict | None] = [None] * size
    pending = list(tasks)
    while pending:
        now = time.monotonic()
        for task in tuple(pending):
            within_limits = now < task.deadline and not task.oversized
            running = task.process.poll() is None
            if running and within_limits:
                continue
            if not within_limits:
                task.terminated = True
            if running:
                _terminate(task.process)
            elif not task.reader_done.is_set() and within_limits:
                continue
            results[task.index] = _parse_output(task)
            pending.remove(task)
        if pending:
            next_deadline = min(task.deadline for task in pending)
            sleep_for = max(0.0, next_deadline - time.monotonic())
            time.sleep(min(PROCESS_POLL_SECONDS, sleep_for))
    return results


def _run_json_commands(
    commands: Sequence[Sequence[str]],
    input_bytes: bytes,
    deadline: float,
    allowances: Sequence[float],
) -> list[dict | None]:
    tasks = []
    for index, (command, allowance) in enumerate(zip(commands, allowances, strict=True)):
        timeout = remaining_timeout(deadline, allowance)
        if timeout <= 0:
            continue
        process_deadline = time.monotonic() + timeout
        task = _spawn(index, command, input_bytes, process_deadline)
        if task is not None:
            tasks.append(task)
    return _collect(tasks, len(commands))


def run_detector_group(
    plugin_root: Path,
    names: Sequence[str],
    payload: dict,
    deadline: float,
    allowances: dict[str, float] = DETECTOR_TIMEOUT_SECONDS,
) -> list[dict | None]:
    try:
        input_bytes = json.dumps(payload).encode()
    except (TypeError, ValueError):
        return [None] * len(names)
    commands = []
    timeouts = []
    indices = []
    for index, name in enumerate(names):
        script = plugin_root / "scripts" / "detectors" / name
        allowance = allowances.get(name)
        if script.is_file() and allowance is not None:
            commands.append((sys.executable, str(script)))
            timeouts.append(allowance)
            indices.append(index)
    compact = _run_json_commands(commands, input_bytes, deadline, timeouts)
    results: list[dict | None] = [None] * len(names)
    for index, result in zip(indices, compact, strict=True):
        results[index] = result
    return results


def run_json_command(
    command: Sequence[str], deadline: float, allowance: float
) -> dict | None:
    return _run_json_commands((command,), b"", deadline, (allowance,))[0]
