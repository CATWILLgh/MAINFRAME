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
from test_build_release import (
    assert_late_failure_preserves_bundle,
    run_dry_run,
    snapshot_tree,
)


DORMANT_DIAGNOSTICS = (
    b'{\n  "schema_version": 1,\n  "events": false,\n  "feedback": false\n}\n'
)


def _target(unit: dict) -> tuple[str, str]:
    target = unit["target"]
    return target["root"], target["path"]


def _expected_install_targets() -> set[tuple[str, str]]:
    profile = load_profiles(REPO)["codex"]
    skills, _ = build_codex.collect_skills(REPO, profile)
    private_methods = build_codex.collect_private_methods(REPO, profile)
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
        ("codex-config", "skills/harness-feedback"),
    }
    targets.update(
        ("codex-config", f"skills/{name}") for name, _ in skills
    )
    targets.update(
        ("codex-config", f"mainframe-agent-methods/{name}")
        for name, _ in private_methods
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
    private_methods = build_codex.collect_private_methods(REPO, profile)
    agents = build_codex.collect_agents(REPO)
    paths = {
        "AGENTS.md",
        "credentials-index.md",
        "diagnostics.json",
        "hooks.json",
        "mainframe-hook.sh",
        "rules/mainframe.rules",
        "skills/harness-feedback/SKILL.md",
        "skills/harness-feedback/feedback.py",
    }
    paths.update(
        f"skills/{name}/{relative.as_posix()}"
        for name, files in skills
        for relative in files
    )
    paths.update(
        f"mainframe-agent-methods/{name}/{relative.as_posix()}"
        for name, files in private_methods
        for relative in files
    )
    paths.update(f"agents/{name}.toml" for name, _ in agents)
    paths.update(
        f"gates/{group}/{relative.as_posix()}"
        for group in ("detectors", "rules")
        for relative in source_files(REPO / f"core/gates/{group}")
    )
    return paths


def _expected_resources() -> dict[str, dict]:
    return {
        "codex.credentials-index": {
            "id": "codex.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "codex-config",
                "path": "credentials-index.md",
            },
            "observation": "supported",
            "apply": "unimplemented",
        },
        "codex.diagnostics": {
            "id": "codex.diagnostics",
            "strategy": "exact-json-document",
            "source": "diagnostics.json",
            "target": {
                "root": "codex-config",
                "path": "mainframe/diagnostics.json",
            },
            "observation": "supported",
            "apply": "supported",
        },
        "codex.hook-trust": {
            "id": "codex.hook-trust",
            "strategy": "manual-action",
            "source": "hooks.json",
            "target": {"root": "codex-config", "path": "hooks.json"},
            "observation": "supported",
            "apply": "unimplemented",
            "external_state": {"kind": "codex-hook-trust-v1"},
        },
    }


def _assert_manifest_contract(output: Path) -> None:
    manifest = release_contract.validate_bundle(output)
    assert manifest["schema_version"] == 5
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
    feedback_unit = next(
        unit for unit in units if unit["id"] == "codex.dev.harness-feedback"
    )
    assert feedback_unit["feature"] == "dev.harness-feedback"
    assert {item["path"] for item in manifest["payload_files"]} == (
        _expected_payload_paths()
    )
    resources = {item["id"]: item for item in manifest["resources"]}
    assert resources == _expected_resources()
    assert manifest["mcp_projections"] == [{
        "id": "codex.mcp.context7",
        "codec": "codex-user-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "codex-config", "path": "config.toml"},
        "map_pointer": "/mcp_servers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "codex-config",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }]


def test_build_materializes_complete_self_contained_codex_bundle():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    build_bundle.build(REPO, output)

    launcher = output / "mainframe-hook.sh"
    detectors = output / "gates/detectors"
    for relative in (
        "AGENTS.md",
        "agents/decision-reviewer.toml",
        "credentials-index.md",
        "diagnostics.json",
        "hooks.json",
        "rules/mainframe.rules",
        "skills/harness-feedback/SKILL.md",
        "skills/harness-feedback/feedback.py",
        "mainframe-agent-methods/decision-review/SKILL.md",
    ):
        assert (output / relative).is_file()
    assert (output / "diagnostics.json").read_bytes() == DORMANT_DIAGNOSTICS
    feedback = (output / "skills/harness-feedback/feedback.py").read_text()
    prose = (output / "skills/harness-feedback/SKILL.md").read_text()
    assert "CODEX_HOME" in feedback
    assert "${CODEX_HOME:-$HOME/.codex}/mainframe/feedback" in prose
    assert "~/.claude" not in feedback + prose
    assert "opencode" not in feedback + prose
    assert "~/.gemini" not in feedback + prose
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert (detectors / "path-validation.py").is_file()
    assert (detectors / "_hooklib.py").is_file()
    assert not (output / "skills/decision-review").exists()
    private_method = output / "mainframe-agent-methods/nextjs-backend-patterns/SKILL.md"
    assert private_method.is_file()
    assert "mainframe-agent-methods/nextjs-backend-patterns/recon.js" in (
        private_method.read_text()
    )
    frontend_agent = (output / "agents/react-frontend-engineer.toml").read_text()
    assert (
        "${CODEX_HOME:-$HOME/.codex}/mainframe-agent-methods/"
        "react-frontend-patterns/recon.js" in frontend_agent
    )
    assert (
        "${CODEX_HOME:-$HOME/.codex}/skills/react-frontend-patterns"
        not in frontend_agent
    )
    credentials = (output / "credentials-index.md").read_text()
    assert "${CODEX_HOME:-$HOME/.codex}/credentials-index.md" in credentials
    assert "~/.claude/credentials-index.md" not in credentials
    plan = (output / "skills/task-workflow/plan-file.md").read_text()
    assert "${CODEX_HOME:-$HOME/.codex}/plans/audit" in plan
    assert "~/.claude/plans" not in plan
    workflow = "\n".join(
        path.read_text()
        for path in sorted((output / "skills/task-workflow").rglob("*.md"))
    )
    assert "~/.codex/plans" not in workflow
    assert "{{mainframe.plans_root}}" not in workflow
    assert ".claude" not in launcher.read_text()
    assert not any(
        path.suffix == ".pyc" or "__pycache__" in path.parts
        for path in output.rglob("*")
    )
    _assert_manifest_contract(output)


def test_bundle_gate_tree_has_no_claude_runtime_paths():
    output = Path(tempfile.mkdtemp()) / "bundle-v2"
    build_bundle.build(REPO, output)

    detector_text = "\n".join(
        path.read_text()
        for path in sorted((output / "gates/detectors").rglob("*.py"))
    )
    assert "~/.claude/" not in detector_text


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
    assert not (user_state.parent / "mainframe/diagnostics.json").exists()
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


def test_late_materialization_failure_preserves_complete_bundle():
    assert_late_failure_preserves_bundle(
        build_bundle,
        REPO,
        Path(tempfile.mkdtemp()) / "bundle-v2",
        "materialize",
    )


def test_late_validation_failure_preserves_complete_bundle():
    assert_late_failure_preserves_bundle(
        build_bundle,
        REPO,
        Path(tempfile.mkdtemp()) / "bundle-v2",
        "validate_bundle",
    )


def test_cli_dry_run_preserves_default_output():
    output = REPO / "dist/codex/bundle-v2"
    before = snapshot_tree(output) if output.exists() else None
    result = run_dry_run(ADAPTER / "build_bundle.py", REPO)
    assert result.stdout == "validated Codex bundle without publishing\n"
    assert (snapshot_tree(output) if output.exists() else None) == before


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
