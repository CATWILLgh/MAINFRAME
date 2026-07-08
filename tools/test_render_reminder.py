#!/usr/bin/env python3
"""Tests for tools/render-reminder.py (needs pyyaml, like the render suite)."""

import importlib.util
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import render_core
import test_render_core as trc

_spec = importlib.util.spec_from_file_location(
    "render_reminder", TOOLS / "render-reminder.py")
render_reminder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_reminder)


def test_path_outside_watched_roots_is_ignored():
    root = trc.rendered_tree()
    assert render_reminder.hint_for(str(root / "docs/note.md"), root) is None
    assert render_reminder.hint_for("/etc/hosts", root) is None
    shutil.rmtree(root)


def test_clean_tree_stays_silent():
    root = trc.rendered_tree()
    target = root / "core/gates/detectors/sample-gate.py"
    assert render_reminder.hint_for(str(target), root) is None
    shutil.rmtree(root)


def test_stale_render_after_core_edit_hints_write():
    root = trc.rendered_tree()
    target = root / "core/gates/detectors/sample-gate.py"
    target.write_text(trc.DETECTOR_BODY + "# changed\n")
    msg = render_reminder.hint_for(str(target), root)
    assert msg is not None and "--write" in msg, msg
    shutil.rmtree(root)


def test_adapter_edit_is_watched_too():
    root = trc.rendered_tree()
    target = root / "adapters/claude-code/gates/hooks.json"
    target.write_text('{"hooks": {"changed": true}}\n')
    msg = render_reminder.hint_for(str(target), root)
    assert msg is not None and "--write" in msg, msg
    shutil.rmtree(root)


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
