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
TOOLS = REPO / "tools"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(TOOLS))

import build_bundle
import build_codex
import release_contract
from adapter_profiles import load_profiles
from bundle_sync import source_files


def _target(unit: dict) -> tuple[str, str]:
    target = unit["target"]
    return target["root"], target["path"]


def _expected_install_targets() -> set[tuple[str, str]]:
    profile = load_profiles(REPO)["codex"]
    skills, _ = build_codex.collect_skills(REPO, profile)
    agents = build_codex.collect_agents(REPO)
    gates = {
        Path(group) / relative
        for group in ("detectors", "rules")
        for relative in source_files(REPO / f"core/gates/{group}")
    }
    targets = {
        ("codex-config", "AGENTS.md"),
        ("codex-config", "hooks.json"),
        ("codex-config", "mainframe-hook.sh"),
        ("codex-config", "rules/mainframe.rules"),
    }
    targets.update(
        ("codex-config", f"skills/{name}") for name, _ in skills
    )
    targets.update(
        ("codex-config", f"agents/{name}.toml") for name, _ in agents
    )
    targets.update(
        ("codex-config", f"gates/{relative.as_posix()}")
        for relative in gates
    )
    return targets


def _expected_payload_paths() -> set[str]:
    profile = load_profiles(REPO)["codex"]
    skills, _ = build_codex.collect_skills(REPO, profile)
    agents = build_codex.collect_agents(REPO)
    paths = {
        "AGENTS.md",
        "credentials-index.md",
        "hooks.json",
        "mainframe-hook.sh",
        "rules/mainframe.rules",
    }
    paths.update(
        f"skills/{name}/{relative.as_posix()}"
        for name, files in skills
        for relative in files
    )
    paths.update(f"agents/{name}.toml" for name, _ in agents)
    paths.update(
        f"gates/{group}/{relative.as_posix()}"
        for group in ("detectors", "rules")
        for relative in source_files(REPO / f"core/gates/{group}")
    )
    return paths


def test_build_materializes_complete_self_contained_codex_bundle():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    build_bundle.build(REPO, output)

    launcher = output / "mainframe-hook.sh"
    detectors = output / "gates/detectors"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert (detectors / "path-validation.py").is_file()
    assert (detectors / "_hooklib.py").is_file()
    assert (output / "gates/rules").is_dir()
    assert (output / "AGENTS.md").is_file()
    assert (output / "rules/mainframe.rules").is_file()
    assert (output / "hooks.json").is_file()
    assert (output / "agents/decision-reviewer.toml").is_file()
    assert (output / "credentials-index.md").is_file()
    credentials_index = (output / "credentials-index.md").read_text()
    assert "${CODEX_HOME:-$HOME/.codex}/credentials-index.md" in credentials_index
    assert "~/.claude/credentials-index.md" not in credentials_index
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
    manifest = release_contract.validate_bundle(output)
    assert manifest["component"] == "codex"
    assert manifest["dependencies"] == ["credential-tools", "mainframe-cli"]
    assert manifest["runtime_profile"] == {
        "config_root": "${CODEX_HOME:-$HOME/.codex}",
        "skills_root": "${CODEX_HOME:-$HOME/.codex}/skills",
        "plans_root": "${CODEX_HOME:-$HOME/.codex}/plans",
        "detectors_root": "${CODEX_HOME:-$HOME/.codex}/gates/detectors",
    }
    units = manifest["install_units"]
    assert {_target(unit) for unit in units} == _expected_install_targets()
    assert all(unit["id"].startswith("codex.") for unit in units)
    assert len({unit["id"] for unit in units}) == len(units)
    assert {item["path"] for item in manifest["payload_files"]} == (
        _expected_payload_paths()
    )
    resources = {item["id"]: item for item in manifest["resources"]}
    assert resources == {
        "codex.credentials-index": {
            "id": "codex.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "codex-config",
                "path": "credentials-index.md",
            },
            "observation": "unimplemented",
            "apply": "unimplemented",
        },
        "codex.hook-trust": {
            "id": "codex.hook-trust",
            "strategy": "manual-action",
            "target": {"root": "codex-config", "path": "hooks.json"},
            "observation": "unimplemented",
            "apply": "unimplemented",
        },
    }


def test_build_isolated_from_user_state_and_other_adapter_bundles():
    sandbox = Path(tempfile.mkdtemp())
    output = sandbox / "codex/bundle-v2"
    user_state = sandbox / "home/.codex/config.toml"
    other_bundle = sandbox / "dist/opencode/bundle-v2/sentinel.txt"
    for path, content in (
        (user_state, "user owned\n"),
        (other_bundle, "other adapter\n"),
    ):
        path.parent.mkdir(parents=True)
        path.write_text(content)

    build_bundle.build(REPO, output)

    assert user_state.read_text() == "user owned\n"
    assert other_bundle.read_text() == "other adapter\n"
    assert not (output / "config.toml").exists()
    assert not (output / "default.rules").exists()


def test_native_validation_failure_precedes_bundle_publication():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("unchanged")
    original = build_codex.validate_rules_native

    def reject(_rules_text: str) -> None:
        raise ValueError("native validation failed")

    build_codex.validate_rules_native = reject
    try:
        try:
            build_bundle.build(REPO, output, validate_native=True)
        except ValueError as exc:
            assert str(exc) == "native validation failed"
        else:
            raise AssertionError("native validation failure was ignored")
    finally:
        build_codex.validate_rules_native = original

    assert sentinel.read_text() == "unchanged"
    assert list(output.iterdir()) == [sentinel]


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
    (codex_home / "mainframe/telemetry").mkdir(parents=True)
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
    foreign_agents = sandbox / "foreign-agents"
    foreign_agents.mkdir()
    agents_marker = foreign_agents / "keep.txt"
    agents_marker.write_text("foreign agents")
    agents_link = output / "agents"
    agents_link.symlink_to(foreign_agents, target_is_directory=True)

    build_bundle.build(REPO, output)

    assert marker.read_text() == "foreign"
    assert skills_marker.read_text() == "foreign skills"
    assert agents_marker.read_text() == "foreign agents"
    assert not detector_link.is_symlink()
    assert not skills_link.is_symlink()
    assert not agents_link.is_symlink()
    assert (detector_link / "path-validation.py").is_file()
    assert (skills_link / "task-workflow/SKILL.md").is_file()
    assert (agents_link / "decision-reviewer.toml").is_file()


def test_rebuild_does_not_follow_managed_file_symlinks():
    sandbox = Path(tempfile.mkdtemp())
    output = sandbox / "bundle-v2"
    output.mkdir()
    foreign_launcher = sandbox / "foreign-launcher"
    foreign_manifest = sandbox / "foreign-manifest"
    foreign_credentials = sandbox / "foreign-credentials"
    foreign_launcher.write_text("keep launcher")
    foreign_manifest.write_text("keep manifest")
    foreign_credentials.write_text("keep credentials")
    (output / "mainframe-hook.sh").symlink_to(foreign_launcher)
    (output / "bundle.json").symlink_to(foreign_manifest)
    (output / "credentials-index.md").symlink_to(foreign_credentials)

    build_bundle.build(REPO, output)

    assert foreign_launcher.read_text() == "keep launcher"
    assert foreign_manifest.read_text() == "keep manifest"
    assert foreign_credentials.read_text() == "keep credentials"
    assert not (output / "mainframe-hook.sh").is_symlink()
    assert not (output / "bundle.json").is_symlink()
    assert not (output / "credentials-index.md").is_symlink()


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
