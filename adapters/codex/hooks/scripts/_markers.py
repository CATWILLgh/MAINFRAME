"""Suppression-marker and debug-residue detector sets.

Single source of truth for the two suppression hooks
(scan-suppression-markers.py + stop-gate-suppression-markers.py), which
previously duplicated these verbatim (ticket cb173a75 — the stop-gate file
carried a "keep in sync" comment). Importable so the regexes are unit-testable.
Stdlib only.
"""

import re

import comment_extract as ce

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

# These forms only have meaning inside comments/docstrings. Searching the raw
# file would turn ordinary strings such as `"TODO"` or `"# noqa"` into a
# completion-blocking false positive.
COMMENT_MARKERS = MARKERS[:6]
CODE_MARKERS = MARKERS[6:]

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


def marker_counts(text, file_ext, file_path=None):
    """Count each disallowed marker label in one source text."""
    comments = "\n".join(value for _, value, _ in ce.extract(text, file_ext))
    counts = {
        label: len(rx.findall(comments)) for label, rx in COMMENT_MARKERS
    }
    counts.update({label: len(rx.findall(text)) for label, rx in CODE_MARKERS})
    counts.update({
        label: len(rx.findall(text))
        for label, rx, extensions in DEBUG_RESIDUE
        if file_ext in extensions
    })
    return {label: count for label, count in counts.items() if count}

# Process-narration comment forms (Clean Code Position/Phase Marker + Nonlocal
# Information). Shared by comment-discipline-reminder + its stop-gate. Operates
# on EXTRACTED comment/docstring text (comment_extract), never on raw lines —
# raw UI strings legitimately contain ordinal text.
#
# Ordinal marker: keyword + number, single capital letter, or roman numeral.
# Guards: equation context excluded; pronoun "I" excluded; lowercase letters
# excluded (domain prose risk outweighs the rare lowercase narration).
COMMENT_MARKER_RE = re.compile(
    r"\b(?i:phase|stage|step|part|iteration|milestone)"
    r"\s*[-#:]?\s*(?:\d+|(?!I\b)[A-Z]\b|[IVX]{2,4}\b)(?!\s*[=<>])"
)

# Reference to an ephemeral, out-of-repo process artifact. Always leakage, in
# any context — the one class applied to docstrings as well as comments.
EPHEMERAL_RE = re.compile(
    r"\bas (?:discussed|requested|agreed|we discussed|per our discussion)\b"
    r"|\b(?:per|from|see|in|follow) the (?:plan|to-?do(?: list)?|task list)\b",
    re.IGNORECASE,
)


def is_divider(line):
    """Decorative section divider: a long symbol run, or two 3+ runs."""
    if re.search(r"={4,}|-{4,}|\*{4,}|#{4,}|_{4,}", line):
        return True
    return (len(re.findall(r"={3,}", line)) >= 2
            or len(re.findall(r"-{3,}", line)) >= 2)


def flag_comment(text, is_docstring):
    """True when an extracted comment/docstring is process narration.

    A docstring is leakage only on an ephemeral reference ("Phase 2 of the
    compiler" is ordinary domain prose there); a comment also on an ordinal
    marker or a decorative divider.
    """
    if is_docstring:
        return bool(EPHEMERAL_RE.search(text))
    return (bool(COMMENT_MARKER_RE.search(text))
            or is_divider(text)
            or bool(EPHEMERAL_RE.search(text)))
