"""Suppression-marker and debug-residue detector sets.

Single source of truth for the two suppression hooks
(scan-suppression-markers.py + stop-gate-suppression-markers.py), which
previously duplicated these verbatim (ticket cb173a75 — the stop-gate file
carried a "keep in sync" comment). Importable so the regexes are unit-testable.
Stdlib only.
"""

import re

# (label, compiled regex). Suppression / placeholder markers — language-agnostic.
MARKERS = [
    ("TODO/FIXME/HACK/XXX comment", re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)),
    ("@ts-ignore / @ts-nocheck", re.compile(r"@ts-(?:ignore|nocheck)\b")),
    ("eslint-disable", re.compile(r"eslint-disable\b")),
    ("# type: ignore", re.compile(r"#\s*type:\s*ignore\b")),
    ("# noqa", re.compile(r"#\s*noqa\b")),
    ("pylint: disable", re.compile(r"pylint:\s*disable\b")),
    ("skipped/focused test (.skip/.only/xit/fit)",
     re.compile(r"(?:\.(?:skip|only)\s*\(|\b(?:xit|fit|xdescribe|fdescribe)\s*\()")),
    ("pytest/unittest skip", re.compile(r"@(?:pytest\.mark\.skip|unittest\.skip)")),
]

# Debug residue: (label, compiled regex, extensions). Always-residue subset only;
# console.log / print() are excluded (the global rule exempts CLI output and
# structured logging, so flagging them would be a false-positive firehose).
# Extension-gated to stay 0-FP — e.g. breakpoint('md') is a responsive-design
# helper in frontend code, but the bare Python builtin is always residue.
JS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
PY = {".py", ".pyi"}
PHP = {".php"}
DEBUG_RESIDUE = [
    ("debugger statement", re.compile(r"\bdebugger\b"), JS),
    ("console.debug", re.compile(r"\bconsole\.debug\s*\("), JS),
    ("breakpoint()", re.compile(r"\bbreakpoint\s*\("), PY),
    ("pdb.set_trace()", re.compile(r"\bpdb\.set_trace\s*\("), PY),
    ("var_dump()", re.compile(r"\bvar_dump\s*\("), PHP),
    ("dd()", re.compile(r"\bdd\s*\("), PHP),
]
