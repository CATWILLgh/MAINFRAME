#!/usr/bin/env python3
"""Tests for Claude Code file-agent discovery validation."""

import importlib.util
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "validate-agent.py"
SPEC = importlib.util.spec_from_file_location("validate_agent", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def agent_file(description: str, extra: str = "") -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp())
    path = root / "example-agent.md"
    path.write_text(
        "---\nname: example-agent\n"
        f"description: {description!r}\n{extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    return path


def test_accepts_concise_routing_description():
    path = agent_file("Use for Python backend API implementation. Not for frontend work.")
    assert MODULE.validate(path) == []


def test_repository_agents_satisfy_discovery_contract():
    agents = ROOT / "adapters" / "claude-code" / "agents"
    failures = {
        path.name: MODULE.validate(path)
        for path in sorted(agents.glob("*.md"))
        if MODULE.validate(path)
    }
    assert failures == {}


def test_warns_above_target_and_rejects_above_maximum():
    warning = MODULE.validate(agent_file("a" * 601))
    error = MODULE.validate(agent_file("a" * 801))
    assert warning == [("warning", "description is 601 chars; target is at most 600")]
    assert error == [("error", "description is 801 chars; MAINFRAME maximum is 800")]


def test_rejects_unsupported_when_to_use_and_execution_content():
    issues = MODULE.validate(
        agent_file("Recons the project stack using a preloaded skill.", "when_to_use: API work\n")
    )
    messages = [message for _, message in issues]
    assert "file agents do not support `when_to_use`" in messages
    assert sum("execution detail" in message for message in messages) == 2


def test_rejects_deprecated_todo_write_tool():
    issues = MODULE.validate(agent_file(
        "Use for focused implementation.",
        "tools: Read, TodoWrite, Edit\n",
    ))
    assert issues == [(
        "error",
        "deprecated Claude Code tool `TodoWrite`; omit it or intentionally choose current Task tools",
    )]


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
