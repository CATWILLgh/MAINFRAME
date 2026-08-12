#!/usr/bin/env python3
"""Contract tests for the mainframe-advisor parent-context hook."""

import importlib.util
import json
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = (
    ROOT
    / "adapters"
    / "claude-code"
    / "plugin"
    / "hooks"
    / "scripts"
    / "advisor-context.py"
)
HOOKS = ROOT / "adapters" / "claude-code" / "plugin" / "hooks" / "hooks.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("advisor_context", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(kind, uuid, parent, content, **extra):
    return {
        "type": kind,
        "uuid": uuid,
        "parentUuid": parent,
        "message": {"role": kind, "content": content},
        **extra,
    }


def _write_transcript(path):
    rows = [
        _row("user", "u-old", None, "obsolete branch context"),
        _row("assistant", "a-old", "u-old", [{"type": "text", "text": "old answer"}]),
        _row(
            "assistant",
            "tool",
            "a-old",
            [{"type": "tool_use", "name": "Read", "input": {"secret": "do not inject"}}],
        ),
        _row(
            "user",
            "result",
            "tool",
            [{"type": "tool_result", "content": "large private tool output"}],
        ),
        _row(
            "user",
            "summary",
            "result",
            "agreed DoD and current architecture",
            isCompactSummary=True,
            isVisibleInTranscriptOnly=True,
        ),
        _row("user", "u-new", "summary", [{"type": "text", "text": "review final state"}]),
        {
            "type": "system",
            "subtype": "status",
            "uuid": "connector",
            "parentUuid": "u-new",
            "content": "MF_SYSTEM_CONNECTOR_SENTINEL",
        },
        _row(
            "assistant",
            "thinking",
            "connector",
            [{"type": "thinking", "thinking": "hidden reasoning"}],
        ),
        _row(
            "assistant",
            "a-new",
            "thinking",
            [{"type": "text", "text": "verified affected paths"}],
        ),
        _row(
            "user",
            "meta",
            "a-new",
            "MF_HOOK_PAYLOAD_SENTINEL",
            isMeta=True,
        ),
        _row(
            "assistant",
            "side",
            "a-new",
            [{"type": "text", "text": "sidechain noise"}],
            isSidechain=True,
        ),
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_context_follows_active_visible_chain_from_latest_compaction():
    module = _load_module()
    with tempfile.TemporaryDirectory() as directory:
        transcript = pathlib.Path(directory) / "session.jsonl"
        _write_transcript(transcript)
        context = module.build_context(str(transcript))

    assert context.startswith("MAINFRAME_ADVISOR_CONTEXT_V1")
    assert "agreed DoD and current architecture" in context
    assert "review final state" in context
    assert "verified affected paths" in context
    for excluded in (
        "obsolete branch context",
        "old answer",
        "do not inject",
        "large private tool output",
        "hidden reasoning",
        "MF_SYSTEM_CONNECTOR_SENTINEL",
        "MF_HOOK_PAYLOAD_SENTINEL",
        "sidechain noise",
    ):
        assert excluded not in context


def test_context_is_bounded_and_keeps_summary_plus_newest_message():
    module = _load_module()
    with tempfile.TemporaryDirectory() as directory:
        transcript = pathlib.Path(directory) / "session.jsonl"
        rows = [
            _row("user", "summary", None, "SUMMARY-ANCHOR", isCompactSummary=True),
            _row("assistant", "old", "summary", [{"type": "text", "text": "x" * 9000}]),
            _row("user", "new", "old", "NEWEST-ANCHOR"),
        ]
        transcript.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        context = module.build_context(str(transcript), limit=1200)

    assert len(context) <= 1200
    assert "SUMMARY-ANCHOR" in context
    assert "NEWEST-ANCHOR" in context
    assert len(module._middle_truncate("sensitive" * 100, 10)) == 10


def test_serialized_hook_output_stays_below_claude_context_cap():
    module = _load_module()
    context = (
        "MAINFRAME_ADVISOR_CONTEXT_V1\n"
        + ('русский текст с "кавычками"\\n' * 1000)
        + "\nEND_MAINFRAME_ADVISOR_CONTEXT"
    )
    encoded = module._bounded_hook_output(context)
    decoded = json.loads(encoded)["hookSpecificOutput"]["additionalContext"]

    assert len(encoded) <= module.MAX_HOOK_OUTPUT_CHARS
    assert decoded.startswith("MAINFRAME_ADVISOR_CONTEXT_V1")
    assert decoded.endswith("END_MAINFRAME_ADVISOR_CONTEXT")


def test_context_falls_back_to_active_branch_after_rewind():
    module = _load_module()
    with tempfile.TemporaryDirectory() as directory:
        transcript = pathlib.Path(directory) / "session.jsonl"
        rows = [
            _row("user", "root", None, "active root"),
            _row("assistant", "old", "root", [{"type": "text", "text": "old branch"}]),
            _row(
                "user",
                "abandoned-summary",
                "old",
                "abandoned compact summary",
                isCompactSummary=True,
            ),
            _row("user", "rewind", "root", "active branch after rewind"),
            _row(
                "assistant",
                "leaf",
                "rewind",
                [{"type": "text", "text": "active branch answer"}],
            ),
        ]
        # Compact JSON ensures the reverse marker finder takes the fast-path
        # first and therefore exercises the abandoned-compaction fallback.
        transcript.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
        context = module.build_context(str(transcript))

    assert "active root" in context
    assert "active branch after rewind" in context
    assert "active branch answer" in context
    assert "abandoned compact summary" not in context


def test_hook_is_silent_for_other_agents_and_injects_only_for_advisor():
    with tempfile.TemporaryDirectory() as directory:
        transcript = pathlib.Path(directory) / "session.jsonl"
        _write_transcript(transcript)
        base = {
            "hook_event_name": "SubagentStart",
            "transcript_path": str(transcript),
        }
        other = subprocess.run(
            ["python3", str(SCRIPT)],
            input=json.dumps({**base, "agent_type": "mainframe-researcher"}),
            text=True,
            capture_output=True,
            check=False,
        )
        advisor = subprocess.run(
            ["python3", str(SCRIPT)],
            input=json.dumps({**base, "agent_type": "mainframe-advisor"}),
            text=True,
            capture_output=True,
            check=False,
        )

    assert other.returncode == 0 and other.stdout == "" and other.stderr == ""
    assert advisor.returncode == 0 and advisor.stderr == ""
    output = json.loads(advisor.stdout)
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "SubagentStart"
    assert specific["additionalContext"].startswith("MAINFRAME_ADVISOR_CONTEXT_V1")


def test_missing_transcript_is_explicitly_unavailable():
    module = _load_module()
    assert module.build_context("").startswith("MAINFRAME_ADVISOR_CONTEXT_UNAVAILABLE")


def test_advisor_hook_is_registered_before_general_subagent_telemetry():
    groups = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["SubagentStart"]
    assert groups[0]["matcher"] == "mainframe-advisor"
    command = groups[0]["hooks"][0]
    assert command["args"][-1].endswith("/advisor-context.py")


if __name__ == "__main__":
    test_context_follows_active_visible_chain_from_latest_compaction()
    test_context_is_bounded_and_keeps_summary_plus_newest_message()
    test_serialized_hook_output_stays_below_claude_context_cap()
    test_context_falls_back_to_active_branch_after_rewind()
    test_hook_is_silent_for_other_agents_and_injects_only_for_advisor()
    test_missing_transcript_is_explicitly_unavailable()
    test_advisor_hook_is_registered_before_general_subagent_telemetry()
    print("OK advisor context")
