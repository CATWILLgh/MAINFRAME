#!/usr/bin/env python3
"""Regression test for Python dependency availability before Go integration tests."""

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
DEPENDENCY_COMMAND = "python3 -m pip install tiktoken pyyaml"
GO_TEST_STEP = "- name: Installer lifecycle planner tests"
DARWIN_STEPS = [
    ("uses", "actions/checkout@v6"),
    ("uses", "actions/setup-python@v6"),
    ("run", "python3 -m pip install pyyaml"),
    ("uses", "actions/setup-go@v6"),
    (
        "run",
        "go test -count=1 ./internal/releasecache "
        "./internal/linkworkspace ./internal/hostfs",
    ),
    ("run", "python3 tools/test_build_release.py"),
]


def test_python_build_dependencies_precede_go_integration_tests() -> None:
    workflow = WORKFLOW.read_text()
    dependency = workflow.find(DEPENDENCY_COMMAND)
    go_tests = workflow.find(GO_TEST_STEP)
    assert dependency >= 0
    assert go_tests >= 0
    assert dependency < go_tests
    assert workflow.count(DEPENDENCY_COMMAND) == 1


def test_darwin_pre_sign_job_is_native_targeted_and_minimal() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow["jobs"]["darwin-pre-sign"]
    assert job["runs-on"] == "macos-latest"
    steps = job["steps"]
    assert [step_signature(step) for step in steps] == DARWIN_STEPS
    assert steps[1]["with"] == {"python-version": "3.12"}
    assert steps[3]["with"] == {"go-version-file": "go.mod"}


def step_signature(step: dict[str, object]) -> tuple[str, str]:
    for kind in ("uses", "run"):
        if kind in step:
            return kind, str(step[kind])
    raise AssertionError(f"step has no uses or run action: {step!r}")


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
