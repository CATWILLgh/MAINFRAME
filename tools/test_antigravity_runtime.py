#!/usr/bin/env python3
"""Tier-1 process and budget tests for the Antigravity 2.x bridge."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from importlib import import_module
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO / "adapters" / "antigravity-2" / "gates"
sys.path.insert(0, str(RUNTIME_DIR))
runtime = import_module("mainframe_runtime")


def _detector_root() -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    detector_dir = root / "scripts" / "detectors"
    detector_dir.mkdir(parents=True)
    return root, detector_dir


def test_parallel_execution_preserves_declared_result_order() -> None:
    root, detector_dir = _detector_root()
    rendezvous = root / "rendezvous"
    rendezvous.mkdir()
    body = """import json
import sys
import time
from pathlib import Path

payload = json.load(sys.stdin)
marker = Path(payload["rendezvous"]) / Path(__file__).name
marker.write_text("ready")
deadline = time.monotonic() + 1
while len(list(marker.parent.iterdir())) < 2 and time.monotonic() < deadline:
    time.sleep(0.01)
print(json.dumps({"name": marker.name}))
"""
    names = ("second.py", "first.py")
    for name in names:
        (detector_dir / name).write_text(body)

    results = runtime.run_detector_group(
        root,
        names,
        {"rendezvous": str(rendezvous)},
        time.monotonic() + 2,
        {name: 1.5 for name in names},
    )

    assert results == [{"name": "second.py"}, {"name": "first.py"}]


def test_output_and_spawn_failures_are_isolated() -> None:
    root, detector_dir = _detector_root()
    fixtures = {
        "nonzero.py": "raise SystemExit(3)\n",
        "valid.py": 'print("{\\"ok\\": true}")\n',
        "malformed.py": 'print("not json")\n',
        "oversized.py": f'print("x" * {runtime.MAX_PROCESS_OUTPUT_BYTES + 1})\n',
    }
    for name, body in fixtures.items():
        (detector_dir / name).write_text(body)
    names = (*fixtures, "missing.py")
    results = runtime.run_detector_group(
        root, names, {}, time.monotonic() + 2, {name: 1 for name in names}
    )
    assert results == [None, {"ok": True}, None, None, None]

    original = runtime.subprocess.Popen
    runtime.subprocess.Popen = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    try:
        assert runtime.run_detector_group(
            root, ("valid.py",), {}, time.monotonic() + 1, {"valid.py": 1}
        ) == [None]
    finally:
        runtime.subprocess.Popen = original


def test_process_longer_than_ten_seconds_uses_its_own_allowance() -> None:
    root, detector_dir = _detector_root()
    (detector_dir / "slow.py").write_text(
        "import json, time\ntime.sleep(10.2)\nprint(json.dumps({'ok': True}))\n"
    )

    allowed = runtime.run_detector_group(
        root, ("slow.py",), {}, time.monotonic() + 12, {"slow.py": 11}
    )
    timed_out = runtime.run_detector_group(
        root, ("slow.py",), {}, time.monotonic() + 1, {"slow.py": 0.05}
    )

    assert allowed == [{"ok": True}]
    assert timed_out == [None]


def test_cleanup_wait_is_bounded_when_process_never_reaps() -> None:
    class NeverReaps:
        pid = 999_999

        def wait(self, timeout: float) -> None:
            raise subprocess.TimeoutExpired("never", timeout)

        def kill(self) -> None:
            return None

    original_budget = runtime.PROCESS_CLEANUP_BUDGET_SECONDS
    original_killpg = runtime.os.killpg
    runtime.PROCESS_CLEANUP_BUDGET_SECONDS = 0.05
    runtime.os.killpg = lambda _pid, _signal: None
    started = time.monotonic()
    try:
        runtime._terminate(NeverReaps())
    finally:
        runtime.PROCESS_CLEANUP_BUDGET_SECONDS = original_budget
        runtime.os.killpg = original_killpg
    assert time.monotonic() - started < 0.2


def test_timeout_kills_detector_process_group() -> None:
    if os.name != "posix":
        return
    root, detector_dir = _detector_root()
    child_pid = root / "child.pid"
    (detector_dir / "timeout.py").write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open({str(child_pid)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(30)\n"
    )

    result = runtime.run_detector_group(
        root, ("timeout.py",), {}, time.monotonic() + 0.3, {"timeout.py": 0.2}
    )

    assert result == [None]
    pid = int(child_pid.read_text())
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        status = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True
        ).stdout.strip()
        if status in {"", "Z"}:
            break
        time.sleep(0.02)
    else:
        raise AssertionError("timed-out detector descendant is still running")


def test_event_and_handler_budgets_cover_detector_contracts() -> None:
    for event, names in runtime.EVENT_DETECTORS.items():
        longest = max((runtime.DETECTOR_TIMEOUT_SECONDS[name] for name in names), default=0)
        assert runtime.EVENT_BUDGET_SECONDS[event] >= longest
        assert runtime.HANDLER_TIMEOUT_SECONDS[event] > runtime.EVENT_BUDGET_SECONDS[event]
    assert runtime.HANDLER_MARGIN_SECONDS > runtime.PROCESS_CLEANUP_BUDGET_SECONDS
    assert runtime.DETECTOR_TIMEOUT_SECONDS["nodejs-security-stop-gate.py"] >= 145
    assert runtime.EVENT_BUDGET_SECONDS["Stop"] >= (
        runtime.DETECTOR_TIMEOUT_SECONDS["nodejs-security-stop-gate.py"]
        + runtime.DETECTOR_TIMEOUT_SECONDS["memory-reminder.py"]
    )


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
