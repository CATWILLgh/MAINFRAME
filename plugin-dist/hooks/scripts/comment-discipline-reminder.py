#!/usr/bin/env python3
"""PostToolUse hook: surface a reminder when a code edit adds new comments.

Two layers, both non-blocking (PostToolUse only emits additionalContext):

1. Generic reminder — fires on a net increase in comments. Lists the banned
   comment forms; the model decides if each added comment is genuine WHY or an
   anti-pattern per the CLAUDE.md Engineering rule.

2. Targeted process-leakage callout — fires when an ADDED comment matches a
   high-precision marker shape: an ordinal phase/stage/step marker, a decorative
   section divider, or a reference to an ephemeral plan/todo. This is the
   canonical LLM failure mode: the agent narrates its work plan into permanent
   code (Clean Code "Nonlocal Information" + Position/Phase Marker), referencing
   a plan/todo/doc that exists only in the moment and never lands in the repo.
   The callout quotes the offending line verbatim and overrides the generic one.

Two distinct false positives are avoided:
- Extraction-FP (calling non-comment text a comment) — handled by
  `comment_extract`, a string/char/template-aware extractor that is exact for
  Python (ast + tokenize) and provably FP-free elsewhere, with a line-start-only
  fallback for forms it does not model (fail to silence, never to emit).
- Marker-FP (a legitimate comment flagged) — ordinal phase/step markers are
  process narration in CODE comments but ordinary domain prose in DOCSTRINGS
  ("Phase 2 of the compiler: type-check"). So ordinal/divider markers apply to
  comments only; only the always-leakage ephemeral references apply to
  docstrings.

Attribution is per-edit, not vs git HEAD: the pre-edit file is reconstructed
from the edit's own old/new strings, so a marker added earlier in the session
does not re-fire on every later edit to the same file.

Design: non-blocking; fail-safe (any error -> exit 0); stdlib only.
"""

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comment_extract as ce  # noqa: E402
try:
    from _hooklib import CODE_EXTENSIONS, ext, load_payload, read_git_head, emit_note, run
except Exception:
    sys.exit(0)

_SELF_FILES = {"comment-discipline-reminder.py", "comment_extract.py"}

_MAX_BYTES = 2_000_000

# Ordinal phase/stage/step marker: "Phase 2", "Step 1 of 3", "Stage 3:".
# Digit required (drops FP-prone letter/roman forms). Negative lookahead excludes
# equation context so a domain comment "// phase 0 = DC component" stays silent.
_MARKER_RE = re.compile(
    r"\b(?:phase|stage|step|part|iteration|milestone)\s*[-#:]?\s*\d+(?!\s*[=<>])",
    re.IGNORECASE,
)

# Reference to an ephemeral, out-of-repo process artifact. Always leakage, in any
# context — the one marker class applied to docstrings as well as comments.
_EPHEMERAL_RE = re.compile(
    r"\bas (?:discussed|requested|agreed|we discussed|per our discussion)\b"
    r"|\b(?:per|from|see|in|follow) the (?:plan|to-?do(?: list)?|task list)\b",
    re.IGNORECASE,
)


def _is_divider(line):
    if re.search(r"={4,}|-{4,}|\*{4,}|#{4,}|_{4,}", line):
        return True
    if len(re.findall(r"={3,}", line)) >= 2 or len(re.findall(r"-{3,}", line)) >= 2:
        return True
    return False


def _flag(text, kind):
    """A docstring is leakage only on an ephemeral reference; a comment also on
    an ordinal marker or a decorative divider."""
    if kind == ce.DOCSTRING:
        return bool(_EPHEMERAL_RE.search(text))
    return (bool(_MARKER_RE.search(text))
            or _is_divider(text)
            or bool(_EPHEMERAL_RE.search(text)))


def _read_file(path):
    try:
        if os.path.getsize(path) > _MAX_BYTES:
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _before_after(tool_name, tool_input, file_path):
    """Reconstruct (before, after) full-file text for this single edit."""
    after = _read_file(file_path)
    if tool_name == "Edit":
        old = tool_input.get("old_string", "") or ""
        new = tool_input.get("new_string", "") or ""
        if after is not None and new and new in after:
            return after.replace(new, old, 1), after
        return old, (after if after is not None else new)
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        if after is not None:
            before = after
            for e in reversed(edits):
                new = e.get("new_string", "") or ""
                old = e.get("old_string", "") or ""
                if new and new in before:
                    before = before.replace(new, old, 1)
            return before, after
        old = "".join(e.get("old_string", "") or "" for e in edits)
        new = "".join(e.get("new_string", "") or "" for e in edits)
        return old, new
    if tool_name == "Write":
        content = tool_input.get("content")
        if content is None:
            content = tool_input.get("file_text", "")
        after = content or ""
        before = read_git_head(file_path)
        return (before if before is not None else ""), after
    return "", ""


def _first_line(text):
    body = text.strip()
    return body.splitlines()[0].strip()[:100] if body else ""


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "MultiEdit", "Write"):
        return
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    file_ext = ext(file_path)
    if not file_path or file_ext not in CODE_EXTENSIONS:
        return
    if os.path.basename(file_path) in _SELF_FILES:
        return

    before, after = _before_after(tool_name, tool_input, file_path)

    # Targeted layer — airtight extraction; the precise process-leakage callout.
    after_c = Counter((t, k) for _, t, k in ce.extract(after, file_ext))
    before_c = Counter((t, k) for _, t, k in ce.extract(before, file_ext))
    flagged = [(t, k) for (t, k) in (after_c - before_c).elements() if _flag(t, k)]
    if flagged:
        quoted = "".join(f"  - {_first_line(t)}\n" for t, _ in flagged[:3])
        if len(flagged) > 3:
            quoted += f"  - … {len(flagged) - 3} more\n"
        note = (
            "Process-leakage in an added comment/docstring — it references "
            "ephemeral plan / phase / step state that will not exist for a "
            "future reader (Clean Code \"Nonlocal Information\" + Position/Phase "
            "Marker, both banned by the engineering rule):\n"
            + quoted +
            "Cut the phase/stage/step/plan reference and let the code stand on "
            "its own. Keep ONLY if it is genuine domain WHY (e.g. a real signal "
            "\"phase 0\"), not narration of your work plan. A temporary "
            "workaround belongs in a ticket (surface-ticket skill), not a "
            "comment. This is a reminder, not a block."
        )
        emit_note("PostToolUse", note)
        return

    # Generic nudge — a low-stakes line-start signal, kept alive even on files
    # the airtight extractor skips (.tsx/.rb, heredoc). Docstrings and inline/
    # block comments are intentionally out of this count; targeted never uses it.
    la = Counter(t for _, t, _ in ce.extract_lenient(after, file_ext))
    lb = Counter(t for _, t, _ in ce.extract_lenient(before, file_ext))
    n = sum((la - lb).values())
    if n == 0:
        return
    plural = "s" if n > 1 else ""
    note = (
        f"Heads-up: this change added {n} new comment{plural}. Per the "
        "engineering rule (default to writing no comments — only comment the WHY "
        "that is non-obvious), check each against the banned forms: Position/"
        "Phase Marker (\"// === Phase B ===\", \"// Step 1 of 3\"), Journal/"
        "Byline (\"// added 2024-01-15 for X\"), Redundant Paraphrase (\"// "
        "increments i\"), Nonlocal Information (facts about other modules, "
        "references to a plan/todo not in the repo), Mandated boilerplate, Noise "
        "(decorative lines, \"// end of if\"). If a comment captures genuine WHY "
        "(hidden constraint, subtle invariant, workaround for a specific bug) — "
        "keep it, short: one sentence per non-obvious WHY. Otherwise remove "
        "before declaring done. This is a reminder, not a block."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
