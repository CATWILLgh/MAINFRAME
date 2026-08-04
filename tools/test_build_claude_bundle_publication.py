#!/usr/bin/env python3
"""Publication-safety tests for the Claude Code bundle."""

from __future__ import annotations

import test_build_claude_bundle as base


def test_optional_rules_absence_removes_stale_rules():
    sandbox = base._sandbox()
    output = sandbox / "bundle-v2"
    root = base._fixture_root(sandbox, rules=False)
    base._write(output / "rules/stale.md", "stale\n")

    base.build_bundle.build(root, output)
    manifest = base.build_bundle.validate_bundle(output)

    assert not (output / "rules").exists()
    assert all(".rule." not in unit["id"] for unit in manifest["install_units"])


def test_rebuild_removes_stale_payload_and_does_not_follow_symlinks():
    sandbox = base._sandbox()
    root = base._fixture_root(sandbox)
    output = sandbox / "bundle-v2"
    foreign = sandbox / "foreign"
    foreign.mkdir()
    marker = foreign / "keep.txt"
    marker.write_text("foreign")
    output.mkdir()
    (output / "plugin").symlink_to(foreign, target_is_directory=True)
    base._write(output / "obsolete.txt", "stale\n")

    base.build_bundle.build(root, output)

    assert marker.read_text() == "foreign"
    assert not (output / "plugin").is_symlink()
    assert (output / "plugin/SKILL.md").is_file()
    assert not (output / "obsolete.txt").exists()


def test_late_materialization_failure_preserves_complete_bundle():
    sandbox = base._sandbox()
    base.assert_late_failure_preserves_bundle(
        base.build_bundle,
        base._fixture_root(sandbox),
        sandbox / "bundle-v2",
        "materialize",
    )


def test_late_validation_failure_preserves_complete_bundle():
    sandbox = base._sandbox()
    base.assert_late_failure_preserves_bundle(
        base.build_bundle,
        base._fixture_root(sandbox),
        sandbox / "bundle-v2",
        "validate_bundle",
    )


def _run_all() -> None:
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
