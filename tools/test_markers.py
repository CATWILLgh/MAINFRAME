#!/usr/bin/env python3
"""Unit tests for the suppression `_markers` detector sets.

Closes the cb173a75 TDD debt: the regexes were untestable while embedded as
script-locals. Run: `python3 tools/test_markers.py` (exit 0 = pass). Stdlib only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "plugin-dist", "hooks", "scripts"))
import _markers  # noqa: E402


def labels_for(text, ext):
    """Mirror the hooks' matching: labels firing for (text, extension)."""
    found = [lbl for lbl, rx in _markers.MARKERS if rx.search(text)]
    found += [lbl for lbl, rx, exts in _markers.DEBUG_RESIDUE
              if ext in exts and rx.search(text)]
    return found


def has(text, ext, needle):
    return any(needle in lbl for lbl in labels_for(text, ext))


def test_markers_catch():
    assert has("// TODO: fix", ".ts", "TODO")
    assert has("# FIXME later", ".py", "TODO")  # same label, IGNORECASE
    assert has("// @ts-ignore", ".ts", "ts-ignore")
    assert has("x = 1  # type: ignore", ".py", "type: ignore")
    assert has("y = 2  # noqa", ".py", "noqa")
    assert has("it.skip('x', ...)", ".ts", "skipped")
    assert has("@pytest.mark.skip", ".py", "pytest")


def test_debug_residue_catch_per_language():
    assert has("  debugger;", ".ts", "debugger")
    assert has("console.debug(x)", ".ts", "console.debug")
    assert has("    breakpoint()", ".py", "breakpoint")
    assert has("pdb.set_trace()", ".py", "pdb.set_trace")
    assert has("var_dump($x)", ".php", "var_dump")
    assert has("$u->dd()", ".php", "dd()")


def test_extension_gating():
    # breakpoint( fires only in Python, NOT in frontend (responsive helper)
    assert has("breakpoint()", ".py", "breakpoint")
    assert not has("breakpoint('md')", ".tsx", "breakpoint")
    # debugger fires only in JS, not Python (the word as a substring)
    assert has("debugger;", ".ts", "debugger")
    assert not has("debugger_url = 1", ".py", "debugger")


def test_zero_false_positives():
    # console.log / print() / logger are deliberately NOT patterns
    assert labels_for("console.log(x)", ".ts") == []
    assert labels_for("print('hi')", ".py") == []
    assert labels_for("logger.debug('x')", ".py") == []
    assert labels_for("const x = 1", ".ts") == []


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK _markers — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
