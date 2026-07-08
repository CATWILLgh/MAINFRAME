#!/usr/bin/env python3
"""Tests for tools/render_core.py (stdlib only, hand-rolled runner).

Fixture trees are built in a tmp dir shaped like the repo (core/ + adapters/
sources, plugin-dist/ render targets); one integration test runs `check`
against the real repo, which must be drift-free on a clean tree.
"""

import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import render_core

MAPPINGS = [
    ("core/gates/detectors", "plugin-dist/hooks/scripts"),
    ("adapters/claude-code/gates/run-hook.sh", "plugin-dist/hooks/scripts/run-hook.sh"),
    ("core/gates/rules", "plugin-dist/hooks/rules"),
    ("adapters/claude-code/gates/hooks.json", "plugin-dist/hooks/hooks.json"),
]

DETECTOR_BODY = "import sys\n# guarded by core/gates conventions\nsys.exit(0)\n"
LIB_BODY = "VERSION = 1\n"
RULE_BODY = "rules: []\n"
WRAPPER_BODY = "#!/bin/sh\nexit 0\n"
HOOKS_JSON_BODY = '{"hooks": {}}\n'


def make_sources(root: Path) -> None:
    det = root / "core/gates/detectors"
    det.mkdir(parents=True)
    (det / "sample-gate.py").write_text(DETECTOR_BODY)
    (det / "_lib.py").write_text(LIB_BODY)
    rules = root / "core/gates/rules"
    rules.mkdir(parents=True)
    (rules / "rule.yml").write_text(RULE_BODY)
    adapter = root / "adapters/claude-code/gates"
    adapter.mkdir(parents=True)
    (adapter / "run-hook.sh").write_text(WRAPPER_BODY)
    (adapter / "hooks.json").write_text(HOOKS_JSON_BODY)


def fresh_tree() -> Path:
    root = Path(tempfile.mkdtemp(prefix="render-core-test-"))
    make_sources(root)
    return root


def rendered_tree() -> Path:
    root = fresh_tree()
    render_core.write(root, MAPPINGS)
    return root


def test_write_materializes_targets():
    root = fresh_tree()
    copied = render_core.write(root, MAPPINGS)
    assert (root / "plugin-dist/hooks/scripts/sample-gate.py").read_text() == DETECTOR_BODY
    assert (root / "plugin-dist/hooks/scripts/_lib.py").read_text() == LIB_BODY
    assert (root / "plugin-dist/hooks/scripts/run-hook.sh").read_text() == WRAPPER_BODY
    assert (root / "plugin-dist/hooks/rules/rule.yml").read_text() == RULE_BODY
    assert (root / "plugin-dist/hooks/hooks.json").read_text() == HOOKS_JSON_BODY
    assert len(copied) == 5, copied
    shutil.rmtree(root)


def test_write_is_idempotent():
    root = rendered_tree()
    assert render_core.write(root, MAPPINGS) == []
    shutil.rmtree(root)


def test_check_clean_after_write():
    root = rendered_tree()
    assert render_core.check(root, MAPPINGS) == []
    shutil.rmtree(root)


def test_check_flags_content_drift():
    root = rendered_tree()
    (root / "plugin-dist/hooks/scripts/sample-gate.py").write_text("tampered\n")
    problems = render_core.check(root, MAPPINGS)
    assert any("sample-gate.py" in p and "differs" in p for p in problems), problems
    shutil.rmtree(root)


def test_check_flags_missing_target():
    root = rendered_tree()
    (root / "plugin-dist/hooks/scripts/_lib.py").unlink()
    problems = render_core.check(root, MAPPINGS)
    assert any("_lib.py" in p and "missing" in p for p in problems), problems
    shutil.rmtree(root)


def test_check_flags_orphan_target():
    root = rendered_tree()
    (root / "plugin-dist/hooks/scripts/stray.py").write_text("orphan\n")
    problems = render_core.check(root, MAPPINGS)
    assert any("stray.py" in p and "orphan" in p for p in problems), problems
    shutil.rmtree(root)


def test_deleted_core_source_flags_stale_render_as_orphan():
    root = rendered_tree()
    (root / "core/gates/detectors/sample-gate.py").unlink()
    problems = render_core.check(root, MAPPINGS)
    assert any("sample-gate.py" in p and "orphan" in p for p in problems), problems
    shutil.rmtree(root)


def test_excluded_artifacts_are_ignored():
    root = rendered_tree()
    cache = root / "core/gates/detectors/__pycache__"
    cache.mkdir()
    (cache / "sample-gate.cpython-312.pyc").write_bytes(b"\x00")
    (root / "plugin-dist/hooks/scripts/.DS_Store").write_bytes(b"\x00")
    (root / "plugin-dist/hooks/scripts/x.pyc").write_bytes(b"\x00")
    assert render_core.check(root, MAPPINGS) == []
    shutil.rmtree(root)


def test_lint_flags_naked_render_path_reference():
    root = rendered_tree()
    naked = root / "core/gates/detectors/naked.py"
    naked.write_text("# see plugin-dist/hooks/scripts for the deployed copy\n")
    render_core.write(root, MAPPINGS)
    problems = render_core.check(root, MAPPINGS)
    assert any("naked.py" in p and "self-reference" in p for p in problems), problems
    shutil.rmtree(root)


def test_lint_allows_render_aware_phrasing():
    root = rendered_tree()
    aware = root / "core/gates/detectors/aware.py"
    aware.write_text(
        '"""Source of truth here; rendered to\nplugin-dist/hooks/scripts by render_core."""\n'
    )
    render_core.write(root, MAPPINGS)
    assert render_core.check(root, MAPPINGS) == []
    shutil.rmtree(root)


def test_check_flags_missing_source_dir():
    root = fresh_tree()
    render_core.write(root, MAPPINGS)
    shutil.rmtree(root / "core/gates/rules")
    problems = render_core.check(root, MAPPINGS)
    assert any("core/gates/rules" in p and "source" in p for p in problems), problems
    shutil.rmtree(root)


def test_main_exit_codes():
    root = rendered_tree()
    assert render_core.main(["--root", str(root), "--check"]) == 0
    (root / "plugin-dist/hooks/scripts/sample-gate.py").write_text("tampered\n")
    assert render_core.main(["--root", str(root), "--check"]) == 1
    assert render_core.main(["--root", str(root), "--write"]) == 0
    assert render_core.main(["--root", str(root), "--check"]) == 0
    shutil.rmtree(root)


def test_real_repo_is_drift_free():
    problems = render_core.check(REPO, render_core.GATES_MAPPINGS)
    assert problems == [], problems


def _run_all():
    failures = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
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
    sys.exit(_run_all())
