#!/usr/bin/env python3
"""Unit tests for the suppression `_markers` detector sets.

Closes the cb173a75 TDD debt: the regexes were untestable while embedded as
script-locals. Run: `python3 tools/test_markers.py` (exit 0 = pass). Stdlib only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "adapters/claude-code/plugin", "hooks", "scripts"))
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


def test_comment_marker_digit_and_letter_phases():
    flag = _markers.flag_comment
    assert flag("# Phase 2: wire the API", False)
    assert flag("// Step 1 of 3", False)
    assert flag("# Plan phase B", False)            # letter phase — the user's exact artifact
    assert flag("// Phase B: cleanup", False)
    assert flag("# STEP C", False)
    assert flag("// stage II rollout", False)        # roman numeral


def test_comment_marker_negatives():
    flag = _markers.flag_comment
    assert not flag("# phase 0 = DC component", False)      # equation context
    assert not flag("// the step I described earlier", False)  # pronoun I
    assert not flag("# variant B of the algorithm", False)   # no ordinal keyword
    assert not flag("# fetch retries with backoff", False)   # plain WHY comment
    assert not flag("// phase b lowercase letter", False)    # lowercase letter form skipped


def test_flag_comment_docstring_scope():
    flag = _markers.flag_comment
    # Ordinal markers are ordinary domain prose in docstrings — silent there.
    assert not flag("Phase 2 of the compiler: type-check.", True)
    # Ephemeral plan references are leakage in ANY context.
    assert flag("Added per the plan, see the todo list.", True)
    assert flag("# as discussed, temporary glue", False)


def test_divider_detection():
    flag = _markers.flag_comment
    assert flag("# ==========================", False)
    assert flag("// ----- setup -----", False)
    assert not flag("# a == b means equality", False)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK _markers — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
