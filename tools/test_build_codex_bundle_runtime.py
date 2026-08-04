#!/usr/bin/env python3
"""Runtime-isolation and publication tests for the Codex bundle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import test_build_codex_bundle as base


REPO = base.REPO
build_bundle = base.build_bundle


def test_real_blocking_detector_runs_without_other_adapter_trees():
    sandbox = Path(tempfile.mkdtemp())
    home = sandbox / "home"
    project = sandbox / "project"
    output = sandbox / "codex/bundle-v2"
    home.mkdir()
    project.mkdir()
    build_bundle.build(REPO, output)

    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(sandbox / "codex"))
    payload = json.dumps({
        "cwd": str(project),
        "tool_name": "Bash",
        "tool_input": {"command": f"rm -rf {sandbox / 'outside'}"},
    })
    proc = subprocess.run(
        [str(output / "mainframe-hook.sh"), "PreToolUse", "path-validation.py"],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    decision = json.loads(proc.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "ask"
    assert not (home / ".claude").exists()
    assert not (home / ".config/opencode").exists()


def test_bundle_telemetry_uses_only_codex_local_state():
    sandbox = Path(tempfile.mkdtemp())
    home = sandbox / "home"
    project = sandbox / "project"
    codex_home = sandbox / "codex"
    output = codex_home / "bundle-v2"
    home.mkdir()
    project.mkdir()
    (codex_home / "mainframe").mkdir(parents=True)
    (codex_home / "mainframe/diagnostics.json").write_text(
        '{"schema_version":1,"events":true,"feedback":false}\n'
    )
    (home / ".claude/mainframe/telemetry").mkdir(parents=True)
    build_bundle.build(REPO, output)

    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home))
    payload = json.dumps({
        "hook_event_name": "SessionStart",
        "cwd": str(project),
        "session_id": "codex-isolation-test",
        "source": "startup",
    })
    proc = subprocess.run(
        [sys.executable, str(output / "gates/detectors/telemetry.py")],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert (codex_home / "mainframe/telemetry/telemetry.db").is_file()
    assert not (home / ".claude/mainframe/telemetry/telemetry.db").exists()
    hooklib = (output / "gates/detectors/_hooklib.py").read_text()
    assert ".claude/mainframe/diagnostics.json" not in hooklib


def test_bundle_hook_does_not_enable_telemetry_implicitly():
    sandbox = Path(tempfile.mkdtemp())
    home = sandbox / "home"
    project = sandbox / "project"
    codex_home = sandbox / "codex"
    output = codex_home / "bundle-v2"
    home.mkdir()
    project.mkdir()
    build_bundle.build(REPO, output)

    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home))
    payload = json.dumps({
        "hook_event_name": "SessionStart",
        "cwd": str(project),
        "session_id": "codex-no-opt-in",
        "source": "startup",
    })
    proc = subprocess.run(
        [str(output / "mainframe-hook.sh"), "SessionStart", "telemetry.py"],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert not (codex_home / "mainframe/telemetry").exists()


def test_rebuild_removes_stale_files_from_the_managed_bundle():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    stale_files = (
        output / "obsolete.txt",
        output / "agents/obsolete.toml",
        output / "gates/detectors/obsolete.py",
        output / "gates/rules/obsolete.yml",
        output / "rules/obsolete.rules",
        output / "skills/obsolete/SKILL.md",
    )
    for path in stale_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale")
    stale_link = output / "gates/detectors/broken-link.py"
    stale_link.symlink_to(output / "missing.py")

    build_bundle.build(REPO, output)

    assert not any(path.exists() for path in stale_files)
    assert not stale_link.is_symlink()


def test_build_rejects_a_redirected_bundle_root_without_touching_target():
    sandbox = Path(tempfile.mkdtemp())
    foreign = sandbox / "foreign"
    foreign.mkdir()
    marker = foreign / "keep.txt"
    marker.write_text("foreign")
    output = sandbox / "bundle-v2"
    output.symlink_to(foreign, target_is_directory=True)

    try:
        build_bundle.build(REPO, output)
    except ValueError as exc:
        assert "bundle output must be a real directory" in str(exc)
    else:
        raise AssertionError("redirected bundle root was accepted")

    assert marker.read_text() == "foreign"
    assert output.is_symlink()


def _run_all():
    failures = 0
    tests = [
        (name, function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    for name, function in tests:
        try:
            function()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
