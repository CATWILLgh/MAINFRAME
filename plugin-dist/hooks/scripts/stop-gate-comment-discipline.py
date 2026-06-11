#!/usr/bin/env python3
"""Stop hook: hard gate against process-narration comments added vs `git HEAD`.

The non-blocking per-edit reminder (comment-discipline-reminder.py) can be
ignored mid-run; this gate is the turn-end backstop, mirroring the suppression
stop-gate. It diffs EXTRACTED comments/docstrings (comment_extract — never raw
lines, so UI strings with ordinal text stay silent) between the working tree
and HEAD, and blocks the stop when an added one matches the shared
process-narration detectors in `_markers.flag_comment`.

Self-loop-guarded; fail-open on git/lib failure (any error -> exit 0).
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import comment_extract as ce
    from _hooklib import (CODE_EXTENSIONS, HUB_HOOK_FILES, changed_files,
                          emit_block, ext, load_payload, log_event,
                          read_git_head, run, stop_guard_cwd)
    from _markers import flag_comment
except Exception:
    sys.exit(0)

# Hub detector files legitimately carry narration-shaped fixtures/patterns.
_SELF_FILES = HUB_HOOK_FILES | {"comment_extract.py",
                                "comment-discipline-reminder.py",
                                "stop-gate-comment-discipline.py"}
_MAX_BYTES = 2_000_000
_MAX_QUOTED = 5


def _added_flagged(cwd):
    """(basename, first_line) per flagged comment added vs HEAD, across the
    working-tree diff. Empty if git is unavailable."""
    rows = []
    for path in changed_files(cwd, CODE_EXTENSIONS):
        if os.path.basename(path) in _SELF_FILES:
            continue
        try:
            if os.path.getsize(path) > _MAX_BYTES:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                after = fh.read()
        except Exception:
            continue
        before = read_git_head(path) or ""
        e = ext(path)
        after_c = Counter((t, k) for _, t, k in ce.extract(after, e))
        before_c = Counter((t, k) for _, t, k in ce.extract(before, e))
        for text, kind in (after_c - before_c).elements():
            if flag_comment(text, kind == ce.DOCSTRING):
                first = text.strip().splitlines()[0].strip()[:100]
                rows.append((os.path.basename(path), first))
    return rows


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    rows = _added_flagged(cwd)
    if not rows:
        return
    quoted = "".join(f"  {f}: {t}\n" for f, t in rows[:_MAX_QUOTED])
    more = f"  …and {len(rows) - _MAX_QUOTED} more\n" if len(rows) > _MAX_QUOTED else ""
    reason = (
        f"comment-discipline-stop-gate: {len(rows)} process-narration "
        "comment(s)/docstring(s) added in the working-tree diff vs HEAD:\n"
        + quoted + more +
        "These narrate the work process (ordinal phase/step markers, decorative "
        "dividers, references to an ephemeral plan/todo) and carry no meaning "
        "for a future reader — banned by the engineering comment rule. Remove "
        "them (or rephrase into genuine domain WHY) before stopping the turn."
    )
    emit_block(reason)
    log_event("incident", {"hook": "stop-gate-comment-discipline",
                           "rule_id": "process-leakage",
                           "count": len(rows)}, payload)


if __name__ == "__main__":
    run(main)
