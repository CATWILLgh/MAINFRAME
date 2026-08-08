#!/usr/bin/env python3
"""PostToolUse hook: nudge new tickets to a random hex id, not sequential NNN.

The `surface-ticket` skill allocates ticket ids as a random 8-hex token
(`openssl rand -hex 4`) so two branches or agents never collide on the same id.
Agents nonetheless slip back to the legacy `NNN-` sequential scheme by
pattern-matching existing tickets — a regression the skill warns about in prose
but cannot mechanically prevent. This hook is the backstop: on a Write that
creates `docs/tickets/<id>-<slug>.md` whose id is short decimal (NNN, not an
8-char hex token), it emits a non-blocking note to regenerate the id as hex and
rename. Sequential ids collide under concurrent / multi-branch creation and need
a full-dir max-scan to allocate; hex ids need neither.

Fires on Write only — a new ticket is created with Write, and editing a legacy
NNN ticket must not nag. Non-blocking (additionalContext only), fail-safe (any
error -> exit 0), stdlib.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, emit_note, run
except Exception:
    sys.exit(0)

HEX_LEN = 8  # `openssl rand -hex 4` -> 8 hex chars


def _is_sequential_id(basename):
    """True when the leading id segment is short decimal (NNN), not an 8-hex token."""
    stem = basename[:-3] if basename.endswith(".md") else basename
    head = stem.split("-", 1)[0]
    return head.isdigit() and len(head) < HEX_LEN


def _is_ticket_path(file_path):
    norm = file_path.replace("\\", "/")
    if "/docs/tickets/" not in norm and not norm.startswith("docs/tickets/"):
        return False
    base = os.path.basename(norm)
    return base.endswith(".md") and base != "README.md"


def main():
    payload = load_payload()
    if payload.get("tool_name") != "Write":
        return
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not _is_ticket_path(file_path):
        return
    base = os.path.basename(file_path.replace("\\", "/"))
    if not _is_sequential_id(base):
        return
    note = (
        f"Heads-up: ticket `{base}` uses a sequential `NNN-` id. The "
        "`surface-ticket` convention allocates ids as a random 8-hex token "
        "(`openssl rand -hex 4`) so independent branches / agents never collide "
        "on the same id — sequential numbers do, and need a full-dir max-scan to "
        "allocate. Generate a fresh hex id, rename the file, and set the "
        "frontmatter `id:` to match. Legacy NNN tickets stay as they are (ids are "
        "stable); this applies to the new one."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
