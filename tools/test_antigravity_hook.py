#!/usr/bin/env python3
"""Tier-1 contract tests for the Antigravity 2.x hook bridge."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
HOOK_DIR = REPO / "adapters" / "antigravity-2" / "gates"
sys.path.insert(0, str(HOOK_DIR))
import mainframe_hook as hook


def bridge() -> hook.Bridge:
    state = Path(tempfile.mkdtemp())
    return hook.Bridge(
        plugin_root=REPO,
        state_dir=state,
        detector_runner=lambda _name, _payload: None,
        memory_loader=lambda _payload: "",
    )


def desktop_payload(**extra: object) -> dict:
    payload = {
        "conversationId": "conversation-1",
        "workspacePaths": ["/work/project-b", "/work/project-a"],
        "transcriptPath": "/Users/test/.gemini/antigravity/conversations/c.json",
    }
    payload.update(extra)
    return payload


def test_rejects_cli_and_non_antigravity_transcripts() -> None:
    instance = bridge()
    loaded: list[str] = []
    instance.memory_loader = lambda payload: loaded.append(
        str(payload["transcriptPath"])
    ) or "desktop memory"
    desktop = desktop_payload()
    cli = {**desktop, "transcriptPath": "/Users/test/.gemini/antigravity-cli/c.json"}
    unrelated = {**desktop, "transcriptPath": "/tmp/c.json"}

    assert "desktop memory" in str(instance.handle("PreInvocation", desktop))
    assert instance.handle("PreInvocation", cli) == {}
    assert instance.handle("PreInvocation", unrelated) == {}
    assert loaded == [desktop["transcriptPath"]]


def test_pre_tool_translates_and_enforces_strongest_verdict() -> None:
    calls: list[tuple[str, dict]] = []

    def detector(name: str, payload: dict) -> dict | None:
        calls.append((name, payload))
        if name == "path-validation.py":
            return {
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "unsafe path",
                }
            }
        return None

    instance = bridge()
    instance.detector_runner = detector
    result = instance.handle("PreToolUse", desktop_payload(
        stepIdx=4,
        toolCall={"name": "run_command", "args": {"CommandLine": "rm -rf /", "Cwd": "/work/project-a"}},
    ))

    assert result == {"decision": "deny", "reason": "unsafe path"}
    assert calls[0][1]["tool_name"] == "Bash"
    assert calls[0][1]["tool_input"] == {
        "command": "rm -rf /", "cwd": "/work/project-a"
    }
    assert calls[0][1]["project_dir"] == "/work/project-a"
    assert calls[0][1]["cwd"] == "/work/project-a"


def test_all_official_tool_argument_shapes_are_translated() -> None:
    instance = bridge()
    cases = {
        "write_to_file": (
            {"TargetFile": "/work/a.py", "CodeContent": "new"},
            "Write", {"file_path": "/work/a.py", "content": "new"},
        ),
        "replace_file_content": (
            {"TargetFile": "/work/a.py", "TargetContent": "old", "ReplacementContent": "new"},
            "Edit", {"file_path": "/work/a.py", "old_string": "old", "new_string": "new"},
        ),
        "multi_replace_file_content": (
            {"TargetFile": "/work/a.py", "ReplacementChunks": [
                {"TargetContent": "a", "ReplacementContent": "b"}
            ]},
            "MultiEdit", {"file_path": "/work/a.py", "edits": [
                {"old_string": "a", "new_string": "b"}
            ]},
        ),
    }
    for index, (name, (args, tool_name, tool_input)) in enumerate(cases.items()):
        seen = []
        instance.detector_runner = lambda _name, payload: seen.append(payload)
        instance.handle("PreToolUse", desktop_payload(
            stepIdx=index, toolCall={"name": name, "args": args}
        ))
        assert seen[0]["tool_name"] == tool_name
        assert seen[0]["tool_input"] == tool_input


def test_post_tool_restores_cached_args_and_queues_advisory() -> None:
    observed: list[dict] = []

    def detector(_name: str, payload: dict) -> dict | None:
        observed.append(payload)
        return {"hookSpecificOutput": {"additionalContext": "Review the changed file."}}

    instance = bridge()
    instance.handle("PreToolUse", desktop_payload(
        stepIdx=8,
        toolCall={"name": "write_to_file", "args": {"TargetFile": "/work/a.py", "CodeContent": "x"}},
    ))
    instance.detector_runner = detector
    assert instance.handle("PostToolUse", desktop_payload(stepIdx=8, error=None)) == {}

    assert observed[0]["tool_name"] == "Write"
    assert observed[0]["tool_input"]["file_path"] == "/work/a.py"
    injected = instance.handle("PostInvocation", desktop_payload())
    assert injected == {
        "injectSteps": [{"ephemeralMessage": "Review the changed file."}]
    }
    assert instance.handle("PostInvocation", desktop_payload()) == {}


def test_pre_tool_advisory_is_delivered_after_invocation() -> None:
    instance = bridge()
    instance.detector_runner = lambda _name, _payload: {
        "hookSpecificOutput": {"additionalContext": "Use the safe command form."}
    }

    assert instance.handle("PreToolUse", desktop_payload(
        stepIdx=21,
        toolCall={"name": "run_command", "args": {"CommandLine": "git status"}},
    )) == {}
    assert instance.handle("PostInvocation", desktop_payload()) == {
        "injectSteps": [{"ephemeralMessage": "Use the safe command form."}]
    }


def test_pre_invocation_injects_bounded_memory_with_stable_sentinel() -> None:
    instance = bridge()
    instance.memory_loader = lambda _payload: (
        f"durable fact {hook.MEMORY_SENTINEL_END} injected close"
    )
    result = instance.handle("PreInvocation", desktop_payload())
    message = result["injectSteps"][0]["ephemeralMessage"]

    assert message.startswith(hook.MEMORY_SENTINEL)
    assert message.endswith(hook.MEMORY_SENTINEL_END)
    assert "durable fact" in message
    assert message.count(hook.MEMORY_SENTINEL_END) == 1
    assert len(message.encode()) <= hook.MAX_MEMORY_INJECTION_BYTES


def test_stop_continues_once_only_for_substantive_desktop_session() -> None:
    instance = bridge()
    calls = []

    def detector(name: str, payload: dict) -> dict | None:
        calls.append((name, payload))
        if name == "memory-reminder.py":
            return {"hookSpecificOutput": {"additionalContext": "Persist durable memory."}}
        return None

    instance.detector_runner = detector
    payload = desktop_payload(
        executionNum=3,
        terminationReason="complete",
        transcriptBytes=50_000,
        fullyIdle=True,
    )

    first = instance.handle("Stop", payload)
    second = instance.handle("Stop", payload)
    assert first == {"decision": "continue", "reason": "Persist durable memory."}
    assert second == {}
    memory_call = next(item for item in calls if item[0] == "memory-reminder.py")
    assert memory_call[1]["transcript_bytes"] == 50_000
    assert memory_call[1]["memory_backend"] == "antigravity-2"


def test_stop_aggregates_every_blocker_before_deciding() -> None:
    instance = bridge()
    calls: list[str] = []
    blockers = {
        hook.STOP_DETECTORS[0]: "Fix suppression markers.",
        hook.STOP_DETECTORS[2]: "",
        hook.STOP_DETECTORS[4]: 42,
    }

    def detector(name: str, _payload: dict) -> object:
        calls.append(name)
        if name in blockers:
            return {"decision": "block", "reason": blockers[name]}
        if name == hook.STOP_DETECTORS[1]:
            return {"decision": "allow"}
        return "invalid detector output"

    instance.detector_runner = detector
    result = instance.handle("Stop", desktop_payload(
        executionNum=11, terminationReason="complete", fullyIdle=False,
    ))

    assert result["decision"] == "continue"
    assert calls == list(hook.STOP_DETECTORS)
    assert result["reason"].splitlines()[0] == (
        "Blocking detectors: " + ", ".join(sorted(blockers))
    )
    assert f"[{hook.STOP_DETECTORS[0]}] Fix suppression markers." in result["reason"]
    assert f"[{hook.STOP_DETECTORS[2]}] No reason provided." in result["reason"]
    assert f"[{hook.STOP_DETECTORS[4]}] No reason provided." in result["reason"]


def test_stop_aggregation_is_order_independent_and_bounded() -> None:
    original = hook.STOP_DETECTORS

    def run(order: tuple[str, ...]) -> dict:
        hook.STOP_DETECTORS = order
        instance = bridge()
        instance.detector_runner = lambda name, _payload: {
            "decision": "block", "reason": f"{name}: " + "🙂" * 10_000,
        }
        return instance.handle("Stop", desktop_payload(
            executionNum=12, terminationReason="complete", fullyIdle=True,
        ))

    try:
        forward = run(original)
        reverse = run(tuple(reversed(original)))
    finally:
        hook.STOP_DETECTORS = original

    assert forward == reverse
    assert len(forward["reason"].encode("utf-8")) <= hook.MAX_STOP_REASON_BYTES
    manifest = forward["reason"].splitlines()[0]
    assert manifest == "Blocking detectors: " + ", ".join(sorted(original))


def test_repeated_stop_rechecks_all_blockers_without_looping() -> None:
    instance = bridge()
    calls: list[str] = []

    def detector(name: str, _payload: dict) -> dict:
        calls.append(name)
        if name == "memory-reminder.py":
            raise AssertionError("memory reminder must not run while gates block")
        return {"decision": "block", "reason": name}

    instance.detector_runner = detector
    first_payload = desktop_payload(
        executionNum=13, terminationReason="complete", fullyIdle=True,
    )
    next_payload = {**first_payload, "executionNum": 14}

    assert instance.handle("Stop", first_payload)["decision"] == "continue"
    assert instance.handle("Stop", first_payload) == {}
    assert instance.handle("Stop", next_payload)["decision"] == "continue"
    assert calls == list(hook.STOP_DETECTORS) * 3


def test_unknown_events_and_infrastructure_failures_are_open() -> None:
    instance = bridge()
    assert instance.handle("FutureEvent", desktop_payload()) == {}
    instance.detector_runner = lambda _name, _payload: (_ for _ in ()).throw(OSError())
    assert instance.handle("PreToolUse", desktop_payload(
        stepIdx=1,
        toolCall={"name": "replace_file_content", "args": {}},
    )) == {}


def test_input_cap_and_invalid_json_emit_empty_object() -> None:
    assert hook.process_input(b"not json", bridge(), "Stop") == b"{}\n"
    assert hook.process_input(
        b"x" * (hook.MAX_INPUT_BYTES + 1), bridge(), "Stop"
    ) == b"{}\n"


def test_state_cleanup_enforces_ttl_and_max_file_count() -> None:
    import mainframe_state

    directory = Path(tempfile.mkdtemp())
    now = time.time()
    for index in range(10):
        path = directory / f"recent-{index}.json"
        path.write_text("{}\n")
        os.utime(path, (now - index, now - index))
    stale = directory / "stale.json"
    stale.write_text("{}\n")
    os.utime(stale, (now - 10_000, now - 10_000))

    mainframe_state.prune_state_directory(
        directory, ttl_seconds=100, max_files=4, now=now
    )

    assert stale.exists() is False
    assert sorted(path.name for path in directory.iterdir()) == [
        "recent-0.json", "recent-1.json", "recent-2.json", "recent-3.json"
    ]


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
