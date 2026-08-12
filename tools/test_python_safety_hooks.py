#!/usr/bin/env python3
"""Regression, attribution, and context-cost tests for Python safety hooks."""

import json
import importlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "adapters/claude-code/plugin/hooks/scripts")
SCAN = os.path.join(SCRIPTS, "python-security-scan.py")
STOP = os.path.join(SCRIPTS, "python-security-stop-gate.py")
LAUNCHER = os.path.join(SCRIPTS, "run-hook.sh")
sys.path.insert(0, SCRIPTS)
_python_findings = importlib.import_module("_python_findings")
CURATED_CODES = _python_findings.CURATED_CODES
finding_counts = _python_findings.finding_counts
_marker_state = importlib.import_module("_marker_state")


EXPECTED_CODES = {
    "S102", "S307", "S301", "S506", "S602", "S604", "S501", "S324",
    "S311", "S105", "S106", "S107", "B006", "B008", "B011", "B904",
}


def _run(script, payload, state, env_extra=None):
    env = dict(os.environ, MAINFRAME_MARKER_STATE_DIR=state,
               MAINFRAME_FEEDBACK_NUDGE="0")
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, script], input=json.dumps(payload), capture_output=True,
        text=True, env=env, timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _edit(path, old, new, state, session="s", agent=None, tool="Edit",
          env_extra=None):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new)
    payload = {
        "hook_event_name": "PostToolUse", "session_id": session,
        "agent_id": agent, "cwd": os.path.dirname(path), "tool_name": tool,
        "tool_input": {"file_path": path, "old_string": old, "new_string": new},
    }
    return _run(SCAN, payload, state, env_extra=env_extra)


def _stop(root, state, session="s", agent=None, active=False):
    return _run(STOP, {
        "hook_event_name": "SubagentStop" if agent else "Stop",
        "session_id": session, "agent_id": agent, "cwd": root,
        "stop_hook_active": active,
    }, state)


def _file(root, text="value = 1\n"):
    path = os.path.join(root, "service.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _context(output):
    if not output.strip():
        return ""
    return json.loads(output)["hookSpecificOutput"]["additionalContext"]


def test_curated_rule_set_is_unchanged():
    assert CURATED_CODES == EXPECTED_CODES


def test_new_finding_emits_once_blocks_owner_and_clears_after_fix():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root)
        unsafe = 'password = "hunter2secret"\n'
        code, first, _ = _edit(path, "value = 1\n", unsafe, state)
        assert code == 0 and "S105" in first and "new issue" in first

        after = unsafe + "value = 2\n"
        _, repeated, _ = _edit(path, unsafe, after, state)
        assert repeated == "", "the same finding must not re-enter model context"

        _, blocked, _ = _stop(root, state)
        assert json.loads(blocked)["decision"] == "block" and "S105" in blocked

        safe = 'credential_name = "password"\nvalue = 2\n'
        _edit(path, after, safe, state)
        assert _stop(root, state)[1] == ""


def test_preexisting_finding_stays_silent_and_never_blocks_current_work():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        old = "def f(values=[]):\n    return values\ntail = 1\n"
        path = _file(root, old)
        new = old.replace("tail = 1", "tail = 2")
        assert _edit(path, old, new, state)[1] == ""
        assert _stop(root, state)[1] == ""


def test_state_is_isolated_by_session_and_agent_but_main_aggregates_children():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root)
        _edit(path, "value = 1\n", 'password = "hunter2secret"\n', state,
              session="one", agent="child-a")
        assert _stop(root, state, session="two", agent="child-a")[1] == ""
        assert _stop(root, state, session="one", agent="child-b")[1] == ""
        assert json.loads(_stop(root, state, session="one", agent="child-a")[1])["decision"] == "block"
        assert json.loads(_stop(root, state, session="one")[1])["decision"] == "block"


def test_temporarily_invalid_syntax_does_not_hide_later_finding():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root)
        broken = 'password = "hunter2secret"\nif (\n'
        assert _edit(path, "value = 1\n", broken, state)[1] == ""
        fixed_syntax = 'password = "hunter2secret"\nvalue = 1\n'
        _, output, _ = _edit(path, broken, fixed_syntax, state)
        assert "S105" in output


def test_context_is_bounded_and_contains_no_repeated_policy_essay():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root)
        unsafe = "".join(f'password_{index} = "secret-{index}"\n' for index in range(12))
        _, output, _ = _edit(path, "value = 1\n", unsafe, state)
        note = _context(output)
        assert len(note) < 1800
        assert "OWASP" not in note and "Bandit-aligned" not in note
        assert "…and" in note


def test_force_exclude_behavior_is_preserved_until_separately_approved():
    with tempfile.TemporaryDirectory() as root:
        path = _file(root, 'password = "hunter2secret"\n')
        with open(os.path.join(root, "pyproject.toml"), "w", encoding="utf-8") as handle:
            handle.write('[tool.ruff]\nexclude = ["service.py"]\n')
        assert finding_counts('password = "hunter2secret"\n', ".py", path) == {}


def test_post_tool_scan_runs_ruff_only_for_before_and_after_snapshots():
    real_ruff = shutil.which("ruff")
    assert real_ruff
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root)
        wrappers = os.path.join(root, "bin")
        os.makedirs(wrappers)
        log = os.path.join(root, "ruff-calls")
        wrapper = os.path.join(wrappers, "ruff")
        with open(wrapper, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f"printf x >> {json.dumps(log)}\n"
                f"exec {json.dumps(real_ruff)} \"$@\"\n"
            )
        os.chmod(wrapper, 0o755)
        env = {"PATH": wrappers + os.pathsep + os.environ.get("PATH", "")}
        output = _edit(path, "value = 1\n", 'password = "hunter2secret"\n',
                       state, env_extra=env)[1]
        assert "S105" in output
        with open(log, encoding="utf-8") as handle:
            assert handle.read() == "xx", "one scan each for before and after"


def test_post_update_does_not_rescan_other_owned_files():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        first = os.path.join(root, "first.py")
        second = os.path.join(root, "second.py")
        for path in (first, second):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("unsafe\n")
        old_state = os.environ.get("MAINFRAME_MARKER_STATE_DIR")
        os.environ["MAINFRAME_MARKER_STATE_DIR"] = state
        calls = []

        def counter(text, file_ext, file_path=None):
            calls.append(file_path)
            return {"unsafe": 1} if "unsafe" in text else {}

        try:
            _marker_state.update("session", None, first, {"unsafe": 1},
                                 counter=counter, namespace="cost-test",
                                 current_counts={"unsafe": 1})
            calls.clear()
            _marker_state.update("session", None, second, {"unsafe": 1},
                                 counter=counter, namespace="cost-test",
                                 current_counts={"unsafe": 1})
            assert calls == [], "PostToolUse must not rescan prior files"
        finally:
            if old_state is None:
                os.environ.pop("MAINFRAME_MARKER_STATE_DIR", None)
            else:
                os.environ["MAINFRAME_MARKER_STATE_DIR"] = old_state


def test_missing_ruff_reports_once_and_scanning_recovers_when_available():
    with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as state:
        path = _file(root, 'password = "hunter2secret"\n')
        payload = {
            "hook_event_name": "PostToolUse", "session_id": "missing-ruff",
            "cwd": root, "tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": "value = 1\n",
                           "new_string": 'password = "hunter2secret"\n'},
        }
        env = dict(os.environ, PATH="/usr/bin:/bin", TMPDIR=state,
                   MAINFRAME_MARKER_STATE_DIR=state,
                   MAINFRAME_HOOK_FAILURE_STATE_DIR=os.path.join(state, "failures"),
                   MAINFRAME_FEEDBACK_NUDGE="0")
        first = subprocess.run(
            ["sh", LAUNCHER, "PostToolUse", SCAN], input=json.dumps(payload),
            capture_output=True, text=True, env=env, timeout=30,
        )
        second = subprocess.run(
            ["sh", LAUNCHER, "PostToolUse", SCAN], input=json.dumps(payload),
            capture_output=True, text=True, env=env, timeout=30,
        )
        assert "hook failure" in first.stdout.lower()
        assert second.stdout == ""
        assert "S105" in _run(SCAN, payload, state)[1]


def test_subagent_stop_registration_includes_python_gate_before_telemetry():
    with open(os.path.join(SCRIPTS, "..", "hooks.json"), encoding="utf-8") as handle:
        hooks = json.load(handle)["hooks"]["SubagentStop"][0]["hooks"]
    scripts = [item["args"][-1] for item in hooks]
    assert scripts[-2].endswith("python-security-stop-gate.py")
    assert scripts[-1].endswith("telemetry.py")


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK Python safety hooks — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
