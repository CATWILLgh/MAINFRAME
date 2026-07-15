#!/usr/bin/env python3
"""Regression tests for Claude Code plugin manifest ownership and validation."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import render_core


REPO = Path(__file__).resolve().parent.parent

SOURCE = "adapters/claude-code/plugin.json"
TARGET = "dist/claude-code/plugin/.claude-plugin/plugin.json"
MAPPING = (SOURCE, TARGET)


def _manifest_tree() -> Path:
    root = Path(tempfile.mkdtemp(prefix="claude-plugin-manifest-test-"))
    source = root / SOURCE
    source.parent.mkdir(parents=True)
    source.write_text('{"name": "fixture"}\n')
    render_core.write(root, [MAPPING])
    return root


def test_manifest_mapping_is_part_of_the_production_render() -> None:
    assert MAPPING in render_core.MAPPINGS


def test_authored_and_rendered_manifests_are_byte_identical() -> None:
    source = REPO / SOURCE
    target = REPO / TARGET
    assert source.is_file()
    assert source.read_bytes() == target.read_bytes()


def test_manifest_mapping_detects_every_ownership_failure() -> None:
    mutations = (
        lambda root: (root / TARGET).unlink(),
        lambda root: (root / TARGET).write_text("tampered\n"),
        lambda root: (root / TARGET).with_name("stray.json").write_text("{}\n"),
        lambda root: (root / SOURCE).unlink(),
    )
    for mutate in mutations:
        root = _manifest_tree()
        mutate(root)
        assert render_core.check(root, [MAPPING])
        shutil.rmtree(root)


def test_ci_runs_pinned_strict_validation_in_an_isolated_home() -> None:
    workflow = (REPO / ".github/workflows/ci.yml").read_text()
    assert "CLAUDE_CODE_VERSION: \"2.1.177\"" in workflow
    assert '"@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"' in workflow
    assert "claude plugin validate --strict dist/claude-code/plugin" in workflow
    assert 'HOME="$RUNNER_TEMP/claude-plugin-home"' in workflow
    assert 'CLAUDE_CONFIG_DIR="$RUNNER_TEMP/claude-plugin-home/.claude"' in workflow


def test_version_policy_defers_live_manifest_changes_to_parity_probe() -> None:
    readme = (REPO / "core/README.md").read_text()
    assert "direct skills-directory delivery" in readme
    assert "#f9d6a8b0" in readme


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
