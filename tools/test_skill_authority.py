#!/usr/bin/env python3
"""Contract tests for primary-session skill isolation."""

import importlib.util
import json
import os
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin/hooks/scripts/skill-authority.py"
)
spec = importlib.util.spec_from_file_location("skill_authority", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _payload(skill, agent_id=None, key="skill"):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Skill",
        "tool_input": {key: skill},
    }
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def test_subagent_cannot_load_infrastructure_skill():
    for skill in ("mainframe:infrastructure", "infrastructure"):
        decision, reason = hook.authority_decision(_payload(skill, "agent-123"))
        assert decision == "deny"
        assert "primary session" in reason


def test_alternate_runtime_input_keys_are_supported():
    for key in ("name", "command"):
        decision, _ = hook.authority_decision(
            _payload("mainframe:infrastructure", "agent-123", key=key)
        )
        assert decision == "deny"


def test_primary_session_can_load_infrastructure_skill():
    assert hook.authority_decision(
        _payload("mainframe:infrastructure")
    ) == (None, None)


def test_other_skills_and_other_tools_stay_silent():
    for skill in ("mainframe:testing-strategy", "other:infrastructure", "noop"):
        assert hook.authority_decision(
            _payload(skill, "agent-123")
        ) == (None, None)
    payload = _payload("mainframe:infrastructure", "agent-123")
    payload["tool_name"] = "Read"
    assert hook.authority_decision(payload) == (None, None)


def test_cli_denies_only_subagent_infrastructure_invocation():
    blocked = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(_payload("mainframe:infrastructure", "agent-123")),
        text=True, capture_output=True, timeout=30, check=True,
    )
    result = json.loads(blocked.stdout)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    silent = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(_payload("mainframe:testing-strategy", "agent-123")),
        text=True, capture_output=True, timeout=30, check=True,
    )
    assert silent.stdout == ""


def main():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK skill-authority — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
