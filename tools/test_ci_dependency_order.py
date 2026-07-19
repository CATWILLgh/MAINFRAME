#!/usr/bin/env python3
"""Regression test for Python dependency availability before Go integration tests."""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
DEPENDENCY_COMMAND = "python3 -m pip install tiktoken pyyaml"
GO_TEST_STEP = "- name: Installer lifecycle planner tests"


def test_python_build_dependencies_precede_go_integration_tests() -> None:
    workflow = WORKFLOW.read_text()
    dependency = workflow.find(DEPENDENCY_COMMAND)
    go_tests = workflow.find(GO_TEST_STEP)
    assert dependency >= 0
    assert go_tests >= 0
    assert dependency < go_tests
    assert workflow.count(DEPENDENCY_COMMAND) == 1


def _run_all() -> int:
    failures = 0
    tests = [value for key, value in sorted(globals().items())
             if key.startswith("test_") and callable(value)]
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
