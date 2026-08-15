#!/usr/bin/env python3
"""PostToolUse hook: review newly added comments while their context is fresh.

The generic reminder asks the writer to preserve only durable, code-relevant
rationale. A targeted callout fires when an ADDED comment matches a
   high-precision marker shape: an ordinal phase/stage/step marker, a decorative
   section divider, or a reference to an ephemeral plan/todo. This is the
   common failure mode where a temporary work plan leaks into permanent code.
   The callout identifies its source location without repeating source text in
   hook output.

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

Attribution is per edit and persisted by session and agent for the matching Stop
gate. Unrelated dirty work and other sessions are never attributed to the writer.

Design: non-blocking; fail-safe (any error -> exit 0); stdlib only.
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comment_extract as ce  # noqa: E402
try:
    from _comment_findings import added, display_path, finding_counts
    from _hooklib import (CODE_EXTENSIONS, ext, load_payload, log_hook_signal,
                          read_git_head, emit_note, run)
    from _markers import marker_counts
    from _marker_state import update
    from _notice_state import claim_once
except Exception:
    sys.exit(0)

_SELF_FILES = {"comment-discipline-reminder.py", "comment_extract.py"}

_MAX_BYTES = 2_000_000


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

    before_findings = Counter(finding_counts(before, file_ext))
    after_findings = Counter(finding_counts(after, file_ext))
    deltas = after_findings - before_findings
    _, _, resolved = update(
        payload.get("session_id"), payload.get("agent_id"), file_path,
        dict(deltas), counter=finding_counts, namespace="comments",
    )
    if resolved:
        log_hook_signal(
            __file__, "process-leakage", "resolved", len(resolved), payload
        )

    # Targeted layer — precise candidates, with the original text still present.
    flagged = added(before, after, file_ext)
    if flagged:
        name = display_path(file_path, payload.get("cwd"))
        locations = "".join(
            f"  - {name}:{line} ({kind})\n"
            for _, line, _, kind in flagged[:3]
        )
        if len(flagged) > 3:
            locations += f"  - … {len(flagged) - 3} more\n"
        note = (
            "Review these newly added comments/docstrings; they look dependent "
            "on temporary plan, phase, step, or discussion context:\n"
            + locations +
            "A correct comment must remain understandable from the repository "
            "alone and preserve durable, code-relevant rationale. Rewrite each "
            "candidate to retain that rationale without transient work context, "
            "or remove it only when it contains no durable information."
        )
        emit_note("PostToolUse", note)
        log_hook_signal(
            __file__, "process-leakage", "noted", len(flagged), payload,
            context=note,
        )
        return

    # Generic nudge — a low-stakes line-start signal, kept alive even on files
    # the airtight extractor skips (.tsx/.rb, heredoc). Docstrings and inline/
    # block comments are intentionally out of this count; targeted never uses it.
    la = Counter(t for _, t, _ in ce.extract_lenient(after, file_ext))
    lb = Counter(t for _, t, _ in ce.extract_lenient(before, file_ext))
    added_comments = la - lb
    # The suppression hook already returns a stronger, actionable note for
    # TODOs, diagnostic suppressions, skipped tests, and debug residue. Do not
    # inject a second generic comment reminder for the same text; still count
    # any other comments added by the same tool call.
    n = sum(count for text, count in added_comments.items()
            if not marker_counts(text, file_ext))
    if n == 0 or not claim_once(
            "generic-comment-review", payload.get("session_id"),
            payload.get("agent_id")):
        return
    plural = "s" if n > 1 else ""
    note = (
        f"Review the {n} new comment{plural}. Every comment must preserve "
        "durable, code-relevant rationale that a future reader cannot obtain "
        "from the code alone. Rewrite or remove narration, phase/step labels, "
        "discussion history, and references to transient plans. Do not discard "
        "useful rationale merely to silence this reminder."
    )
    emit_note("PostToolUse", note)
    log_hook_signal(
        __file__, "new-comment-review", "noted", n, payload, context=note
    )


if __name__ == "__main__":
    run(main)
