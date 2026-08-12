#!/usr/bin/env python3
"""Exercise every registered hook concurrently on context-silent inputs."""

import concurrent.futures
import json
import os
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "adapters" / "claude-code" / "plugin"
HOOKS = PLUGIN / "hooks" / "hooks.json"
SESSION_COUNT = 16


def _payload(event, matcher, session, index, workspace):
    payload = {
        "hook_event_name": event,
        "session_id": session,
        "cwd": str(workspace),
    }
    if event == "SessionStart":
        payload.update(source="startup", model="claude-opus-4-1")
    elif event == "UserPromptExpansion":
        payload.update(
            expansion_type="slash_command",
            command_name="mainframe:init",
            command_source="plugin",
        )
    elif event == "UserPromptSubmit":
        payload["prompt"] = "continue"
    elif event in ("PreToolUse", "PostToolUse"):
        payload["tool_use_id"] = f"tool-{session}-{index}"
        if matcher == "Bash":
            payload.update(tool_name="Bash", tool_input={"command": "printf ok"})
        elif matcher == "Skill":
            payload.update(tool_name="Skill", tool_input={"skill": "noop"})
        elif matcher == "Write":
            payload.update(
                tool_name="Write",
                tool_input={
                    "file_path": str(workspace / "note.txt"),
                    "content": "unchanged\n",
                },
            )
        else:
            payload.update(
                tool_name="Edit",
                tool_input={
                    "file_path": str(workspace / "note.txt"),
                    "old_string": "unchanged",
                    "new_string": "unchanged",
                },
            )
        if event == "PostToolUse":
            payload["tool_response"] = {}
    elif event in ("SubagentStart", "SubagentStop"):
        payload.update(
            agent_id=f"agent-{session}",
            agent_type="mainframe-test",
        )
    elif event == "PermissionDenied":
        payload.update(
            tool_name="Bash",
            tool_input={"command": "printf denied"},
            tool_use_id=f"denied-{index}",
            reason="synthetic test",
        )
    elif event == "SessionEnd":
        payload["reason"] = "other"
    return payload


def _registrations():
    data = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]
    rows = []
    for event, groups in data.items():
        for group in groups:
            matcher = group.get("matcher", "*")
            for hook in group.get("hooks", []):
                args = [
                    str(value).replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN))
                    for value in hook.get("args", [])
                ]
                rows.append((event, matcher, [hook.get("command", "sh"), *args]))
    return rows


def test_all_registered_hooks_are_parallel_safe_and_silent_when_not_applicable():
    with tempfile.TemporaryDirectory(prefix="mainframe-hook-parallel-") as directory:
        base = pathlib.Path(directory)
        home = base / "home"
        temp = base / "tmp"
        workspace = base / "workspace"
        for path in (home, temp, workspace):
            path.mkdir()
        (workspace / "note.txt").write_text("unchanged\n", encoding="utf-8")

        env = dict(
            os.environ,
            HOME=str(home),
            TMPDIR=str(temp),
            MAINFRAME_FEEDBACK_NUDGE="0",
            MAINFRAME_INIT_REMINDER_STATE_DIR=str(base / "init-state"),
            MAINFRAME_MARKER_STATE_DIR=str(base / "marker-state"),
            MAINFRAME_FALLOW_STATE_DIR=str(base / "fallow-state"),
            MAINFRAME_LENGTH_STATE_DIR=str(base / "length-state"),
            MAINFRAME_MEMORY_STATE_DIR=str(base / "memory-state"),
            MAINFRAME_HOOK_FAILURE_STATE_DIR=str(base / "failure-state"),
        )
        env.pop("MAINFRAME_TELEMETRY_DB", None)
        registrations = _registrations()
        tasks = [
            (event, matcher, command, f"parallel-{session}", index)
            for session in range(SESSION_COUNT)
            for index, (event, matcher, command) in enumerate(registrations)
        ]

        def invoke(task):
            event, matcher, command, session, index = task
            return subprocess.run(
                command,
                input=json.dumps(_payload(
                    event, matcher, session, index, workspace
                )),
                text=True,
                capture_output=True,
                env=env,
                timeout=30,
                check=False,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
            results = list(pool.map(invoke, tasks))

        failures = [
            result for result in results
            if result.returncode or result.stdout or result.stderr
        ]
        assert not failures, [
            (result.returncode, result.stdout, result.stderr)
            for result in failures[:10]
        ]
        assert not list(temp.glob("mainframe-hook-input.*"))
        assert not list(temp.glob("mainframe-hook-output.*"))
        print(
            f"  parallel hook calls: {len(results)}, "
            "context bytes: 0, stderr bytes: 0"
        )


if __name__ == "__main__":
    test_all_registered_hooks_are_parallel_safe_and_silent_when_not_applicable()
    print("OK hook parallel execution")
