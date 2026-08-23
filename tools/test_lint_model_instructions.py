#!/usr/bin/env python3
"""Focused tests for the model-instruction lexical linter."""

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "lint-model-instructions.py"
SPEC = importlib.util.spec_from_file_location("lint_model_instructions", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def lint(text: str, adapter: str = "claude-code", suffix: str = ".md"):
    directory = Path(tempfile.mkdtemp())
    path = directory / ("test" + suffix)
    path.write_text(text, encoding="utf-8")
    return MODULE.lint_file(adapter, path)


def rules(findings):
    return [item.rule for item in findings]


def test_accepts_real_secret_invariant():
    assert lint("Never expose secret values in replies or logs.\n") == []


def test_rejects_aggressive_claude_discovery_pressure():
    findings = lint(
        "---\nname: research\ndescription: 'CRITICAL: YOU MUST use this skill for research.'\n---\n"
    )
    assert "MI-CLAUDE-001" in rules(findings)
    assert any(item.level == "error" for item in findings)


def test_warns_on_absolute_judgment_call():
    findings = lint("Always search the internet before answering.\n", adapter="codex")
    assert rules(findings) == ["MI-COMMON-004"]
    assert findings[0].level == "warning"


def test_ignores_quoted_hazard_examples():
    assert lint("Replace `CRITICAL: YOU MUST use this tool` with a selection condition.\n") == []


def test_rejects_exposed_reasoning_request_but_accepts_prohibition():
    assert "MI-COMMON-010" in rules(lint("Show your internal reasoning before answering.\n"))
    assert lint("Do not reveal internal reasoning. Return evidence and conclusions.\n") == []


def test_warns_on_broad_standalone_style_label():
    findings = lint("Be concise.\n")
    assert rules(findings) == ["MI-COMMON-005"]
    assert lint("Lead with the result and preserve material evidence and caveats.\n") == []


def test_warns_on_exact_duplicate_instruction_in_one_file():
    line = "Preserve every material constraint and verify the resulting artifact before completion."
    findings = lint(f"{line}\n{line}\n")
    assert rules(findings) == ["MI-COMMON-002"]


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
