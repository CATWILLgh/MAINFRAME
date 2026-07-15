#!/usr/bin/env python3
"""Hermetic tests for the unlinked Codex bundle-v2 projection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters/codex"
sys.path.insert(0, str(ADAPTER))

import build_bundle


def test_build_materializes_self_contained_gate_tree():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    build_bundle.build(REPO, output)

    launcher = output / "mainframe-hook.sh"
    detectors = output / "gates/detectors"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert (detectors / "path-validation.py").is_file()
    assert (detectors / "_hooklib.py").is_file()
    assert (output / "gates/rules").is_dir()
    plan_file = output / "skills/task-workflow/plan-file.md"
    assert plan_file.is_file()
    assert "${CODEX_HOME:-$HOME/.codex}/plans/audit" in plan_file.read_text()
    assert "~/.claude/plans" not in plan_file.read_text()
    workflow_markdown = "\n".join(
        path.read_text()
        for path in sorted((output / "skills/task-workflow").rglob("*.md"))
    )
    assert "~/.codex/plans" not in workflow_markdown
    assert "{{mainframe.plans_root}}" not in workflow_markdown
    assert ".claude" not in launcher.read_text()
    assert not any(
        "__pycache__" in path.parts or path.suffix == ".pyc"
        for path in output.rglob("*")
    )
    manifest = json.loads((output / "bundle.json").read_text())
    assert manifest == {
        "adapter": "codex",
        "config_root": "${CODEX_HOME:-$HOME/.codex}",
        "skills_root": "${CODEX_HOME:-$HOME/.codex}/skills",
        "plans_root": "${CODEX_HOME:-$HOME/.codex}/plans",
        "detectors_root": "${CODEX_HOME:-$HOME/.codex}/gates/detectors",
    }


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


def test_rebuild_removes_stale_files_from_the_managed_bundle():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    stale_files = (
        output / "obsolete.txt",
        output / "gates/detectors/obsolete.py",
        output / "gates/rules/obsolete.yml",
    )
    for path in stale_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale")
    stale_link = output / "gates/detectors/broken-link.py"
    stale_link.symlink_to(output / "missing.py")

    build_bundle.build(REPO, output)

    assert not any(path.exists() for path in stale_files)
    assert not stale_link.is_symlink()


def test_rebuild_replaces_a_redirected_detector_directory_safely():
    sandbox = Path(tempfile.mkdtemp())
    output = sandbox / "bundle-v2"
    foreign = sandbox / "foreign"
    foreign.mkdir()
    marker = foreign / "keep.txt"
    marker.write_text("foreign")
    foreign_skills = sandbox / "foreign-skills"
    foreign_skills.mkdir()
    skills_marker = foreign_skills / "keep.txt"
    skills_marker.write_text("foreign skills")
    detector_link = output / "gates/detectors"
    detector_link.parent.mkdir(parents=True)
    detector_link.symlink_to(foreign, target_is_directory=True)
    skills_link = output / "skills"
    skills_link.symlink_to(foreign_skills, target_is_directory=True)

    build_bundle.build(REPO, output)

    assert marker.read_text() == "foreign"
    assert skills_marker.read_text() == "foreign skills"
    assert not detector_link.is_symlink()
    assert not skills_link.is_symlink()
    assert (detector_link / "path-validation.py").is_file()
    assert (skills_link / "task-workflow/SKILL.md").is_file()


def test_rebuild_does_not_follow_managed_file_symlinks():
    sandbox = Path(tempfile.mkdtemp())
    output = sandbox / "bundle-v2"
    output.mkdir()
    foreign_launcher = sandbox / "foreign-launcher"
    foreign_manifest = sandbox / "foreign-manifest"
    foreign_launcher.write_text("keep launcher")
    foreign_manifest.write_text("keep manifest")
    (output / "mainframe-hook.sh").symlink_to(foreign_launcher)
    (output / "bundle.json").symlink_to(foreign_manifest)

    build_bundle.build(REPO, output)

    assert foreign_launcher.read_text() == "keep launcher"
    assert foreign_manifest.read_text() == "keep manifest"
    assert not (output / "mainframe-hook.sh").is_symlink()
    assert not (output / "bundle.json").is_symlink()


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
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
