#!/usr/bin/env python3
"""Contract tests for adapter-owned runtime roots and text projection."""

import json
import tempfile
from pathlib import Path

from adapter_profiles import (
    CONFIG_ROOT_TOKEN,
    PLAN_ROOT_TOKEN,
    load_profiles,
    project_text,
)


REPO = Path(__file__).resolve().parent.parent


def test_profiles_define_three_isolated_runtime_trees():
    profiles = load_profiles(REPO)
    assert set(profiles) == {"claude-code", "codex", "opencode"}

    foreign_markers = {
        "claude-code": (".codex", "opencode"),
        "codex": (".claude", "opencode"),
        "opencode": (".claude", ".codex"),
    }
    for name, profile in profiles.items():
        assert profile.plans_root == f"{profile.config_root}/plans"
        for value in (
            profile.config_root,
            profile.skills_root,
            profile.plans_root,
            profile.detectors_root,
        ):
            assert not any(marker in value for marker in foreign_markers[name])


def test_projection_resolves_semantic_plan_root_without_leaking_token():
    profiles = load_profiles(REPO)
    source = f"write audit plans below `{PLAN_ROOT_TOKEN}/audit`"

    expected = {
        "claude-code": "~/.claude/plans/audit",
        "codex": "${CODEX_HOME:-$HOME/.codex}/plans/audit",
        "opencode": "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/plans/audit",
    }
    for name, path in expected.items():
        rendered = project_text(source, profiles[name])
        assert path in rendered
        assert PLAN_ROOT_TOKEN not in rendered


def test_projection_resolves_semantic_config_root_without_leaking_token():
    profiles = load_profiles(REPO)
    source = f"index lives below `{CONFIG_ROOT_TOKEN}/credentials-index.md`"
    for profile in profiles.values():
        rendered = project_text(source, profile)
        assert f"`{profile.config_root}/credentials-index.md`" in rendered
        assert CONFIG_ROOT_TOKEN not in rendered


def test_profile_rejects_a_runtime_root_owned_by_another_adapter():
    root = Path(tempfile.mkdtemp())
    source = REPO / "adapters/runtime-profiles.json"
    profiles = json.loads(source.read_text())
    profiles["codex"]["skills_root"] = "~/.claude/skills"
    target = root / "adapters/runtime-profiles.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(profiles))

    try:
        load_profiles(root)
    except ValueError as exc:
        assert "codex skills_root is outside config_root" in str(exc)
    else:
        raise AssertionError("cross-adapter runtime root was accepted")


def test_profile_rejects_parent_traversal_out_of_the_adapter_root():
    root = Path(tempfile.mkdtemp())
    profiles = json.loads(
        (REPO / "adapters/runtime-profiles.json").read_text()
    )
    profiles["codex"]["skills_root"] = (
        "${CODEX_HOME:-$HOME/.codex}/../.claude/skills"
    )
    target = root / "adapters/runtime-profiles.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(profiles))

    try:
        load_profiles(root)
    except ValueError as exc:
        assert "codex skills_root contains a traversal segment" in str(exc)
    else:
        raise AssertionError("runtime root traversal was accepted")


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
