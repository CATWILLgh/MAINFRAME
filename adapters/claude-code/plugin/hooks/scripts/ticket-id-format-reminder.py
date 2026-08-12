#!/usr/bin/env python3
"""PostToolUse hook: nudge new tickets toward the compact ticket filename.

New tickets use an unused random four-character lowercase hexadecimal id and a
descriptive kebab-case slug. Four characters avoid the color-token treatment
observed with eight-character hex strings; checking the directory before use
handles ordinary local collisions without a shared sequential counter.

Fires on Write only. It is deliberately advisory because the ticket body has
already been generated: correction should rename the file and edit frontmatter,
not spend tokens generating the body again. Existing ticket ids remain stable;
their slug is reviewed by the ticket workflow when they are updated.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, emit_note, log_hook_signal, run
except Exception:
    sys.exit(0)

TICKET_NAME_RE = re.compile(
    r"^(?P<id>[0-9a-f]{4})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
FRONTMATTER_ID_RE = re.compile(r"(?m)^id:\s*['\"]?([^'\"\s]+)['\"]?\s*$")


def _frontmatter_id(content):
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end < 0:
        return None
    match = FRONTMATTER_ID_RE.search(content[:end])
    return match.group(1) if match else None


def _is_ticket_path(file_path):
    norm = file_path.replace("\\", "/")
    if "/docs/tickets/" not in norm and not norm.startswith("docs/tickets/"):
        return False
    base = os.path.basename(norm)
    return base.endswith(".md") and base != "README.md"


def _id_is_used_elsewhere(cwd, file_path, ticket_id):
    if not cwd or not ticket_id:
        return False
    tickets_dir = os.path.realpath(os.path.join(cwd, "docs", "tickets"))
    if not os.path.isdir(tickets_dir):
        return False
    current = file_path
    if not os.path.isabs(current):
        current = os.path.join(cwd, current)
    current = os.path.realpath(current)
    prefix = ticket_id + "-"
    for root, dirs, names in os.walk(tickets_dir):
        dirs.sort()
        for name in sorted(names):
            if not name.startswith(prefix) or not name.endswith(".md"):
                continue
            if os.path.realpath(os.path.join(root, name)) != current:
                return True
    return False


def main():
    payload = load_payload()
    if payload.get("tool_name") != "Write":
        return
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not _is_ticket_path(file_path):
        return
    base = os.path.basename(file_path.replace("\\", "/"))
    match = TICKET_NAME_RE.fullmatch(base)
    content = tool_input.get("content")
    if content is None:
        content = tool_input.get("file_text", "")
    document_id = _frontmatter_id(content or "")
    ticket_id = match.group("id") if match else document_id
    collision = _id_is_used_elsewhere(
        payload.get("cwd") or "", file_path, ticket_id
    )
    if match and document_id == match.group("id") and not collision:
        return
    collision_note = " This id already belongs to another ticket." if collision else ""
    note = (
        f"Review ticket filename `{base}`. A new ticket uses an unused random "
        "four-character lowercase hex id (`openssl rand -hex 2`) followed by a "
        "concise descriptive kebab-case slug; its frontmatter `id:` must match. "
        f"{collision_note} "
        "Do not regenerate the ticket body: rename the file and edit only the "
        "id or slug that is wrong. If this Write updated an open ticket, "
        "preserve its stable id and only make the slug accurately describe the "
        "record, updating repository references when it changes. Archived "
        "tickets are immutable."
    )
    emit_note("PostToolUse", note)
    log_hook_signal(
        __file__, "ticket-id-format", "noted", 1, payload, context=note
    )


if __name__ == "__main__":
    run(main)
