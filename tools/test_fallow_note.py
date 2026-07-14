#!/usr/bin/env python3
"""Unit tests for the fallow advisory-note builder (`fallow-quality-note.py`).

Run: `python3 tools/test_fallow_note.py` (exit 0 = pass). Stdlib only. The
fixture mirrors fallow 2.92.1 `--format json` (schema_version 7) captured on a
synthetic project; the builder must tolerate missing keys (schema drifts).
"""

import importlib.util
import os
import sys
import tempfile
import time

sys.dont_write_bytecode = True

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "dist", "claude-code", "plugin", "hooks", "scripts",
                       "fallow-quality-note.py")
spec = importlib.util.spec_from_file_location("fallow_note", _SCRIPT)
fallow_note = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallow_note)


def _report(**over):
    base = {
        "check": {
            "circular_dependencies": [
                {"files": ["src/a.ts", "src/b.ts"], "length": 2}],
            "boundary_violations": [],
            "boundary_call_violations": [],
            "unused_files": [
                {"path": "src/components/ui/calendar.tsx"},
                {"path": "docs/mock.jsx"},
                {"path": "src/lib/helper.test.ts"},
                {"path": "src/lib/dead.ts"},
            ],
        },
        "health": {
            "findings": [
                {"path": "src/big.ts", "name": "big", "line": 1,
                 "cyclomatic": 71, "line_count": 270, "severity": "critical"},
                {"path": "src/ok.ts", "name": "mid", "line": 5,
                 "cyclomatic": 18, "line_count": 60, "severity": "moderate"},
            ],
        },
        "dupes": {"stats": {"clone_groups": 199, "duplication_percentage": 11.2}},
    }
    base.update(over)
    return base


def test_note_contains_conservative_categories():
    note, counts = fallow_note.build_note(_report())
    assert note is not None
    assert "src/a.ts" in note and "src/b.ts" in note          # cycle named
    assert "calendar.tsx" in note and "dead.ts" in note       # unused listed
    assert "big" in note and "270" in note                    # worst critical fn
    assert "199" in note                                      # clones as a number
    assert "not a block" in note                              # advisory framing
    assert counts == {"cycles": 1, "boundaries": 0, "unused_files": 2,
                      "critical": 1, "clone_groups": 199}


def test_docs_and_tests_filtered_from_unused():
    note, counts = fallow_note.build_note(_report())
    assert "docs/mock.jsx" not in note
    assert "helper.test.ts" not in note
    assert counts["unused_files"] == 2


def test_noisy_categories_never_reported():
    rep = _report()
    rep["check"]["unused_dependencies"] = [{"name": "pino-pretty"}]
    rep["check"]["unused_exports"] = [{"export_name": "x"}] * 50
    note, _ = fallow_note.build_note(rep)
    assert "pino-pretty" not in note and "export" not in note.lower()


def test_silence_when_nothing_significant():
    rep = {
        "check": {"circular_dependencies": [], "unused_files": []},
        "health": {"findings": [{"severity": "moderate"}]},
        "dupes": {"stats": {"clone_groups": 3}},   # below the clone threshold
    }
    note, counts = fallow_note.build_note(rep)
    assert note is None and counts == {}


def test_tolerates_garbage_and_missing_keys():
    assert fallow_note.build_note({}) == (None, {})
    assert fallow_note.build_note({"check": None, "health": None}) == (None, {})


def test_throttle_runs_once_per_window():
    d = tempfile.mkdtemp()
    cwd = "/some/project"
    assert fallow_note._throttled(cwd, stamp_dir=d) is False   # first run -> go
    assert fallow_note._throttled(cwd, stamp_dir=d) is True    # immediate retry -> skip
    stamp = os.path.join(d, os.listdir(d)[0])
    old = time.time() - fallow_note.THROTTLE_SECONDS - 5
    os.utime(stamp, (old, old))
    assert fallow_note._throttled(cwd, stamp_dir=d) is False   # window passed -> go


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK fallow-note — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
