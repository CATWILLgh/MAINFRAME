#!/usr/bin/env python3
"""Inject a bounded, visible-only parent transcript into mainframe-advisor.

The hook is stateless and acts only for the named advisor. It follows the
active JSONL ancestry, keeps visible user/assistant text, starts at the latest
compaction summary when present, and excludes thinking, tool traffic, hook
metadata, and sidechains. Failures are handled by run-hook.sh.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, run
except Exception:
    sys.exit(0)

AGENT = "mainframe-advisor"
MARKER = "MAINFRAME_ADVISOR_CONTEXT_V1"
UNAVAILABLE = "MAINFRAME_ADVISOR_CONTEXT_UNAVAILABLE"
MAX_CONTEXT_CHARS = 9_000
MAX_SUMMARY_CHARS = 3_600
MAX_HOOK_OUTPUT_CHARS = 9_900
_COMPACT_MARKER = b'"isCompactSummary":true'


def _latest_compaction_offset(path):
    """Return the line offset of the latest compact summary, or zero."""
    chunk_size = 1024 * 1024
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        suffix = b""
        while position:
            size = min(chunk_size, position)
            position -= size
            handle.seek(position)
            data = handle.read(size) + suffix
            index = data.rfind(_COMPACT_MARKER)
            if index >= 0:
                line_start = data.rfind(b"\n", 0, index) + 1
                return position + line_start
            suffix = data[: min(len(data), 256)]
    return 0


def _text_blocks(content):
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        block.get("text", "")
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]


def _read_nodes(path, offset):
    nodes = {}
    leaf = None
    with open(path, "rb") as handle:
        handle.seek(offset)
        for raw in handle:
            try:
                row = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            uuid = row.get("uuid")
            if not isinstance(uuid, str) or not uuid:
                continue
            kind = row.get("type")
            conversational = kind in ("user", "assistant")
            visible = (
                conversational
                and not row.get("isMeta")
                and not row.get("isSidechain")
            )
            message = row.get("message") or {}
            role = message.get("role")
            texts = _text_blocks(message.get("content")) if visible else []
            compact = row.get("isCompactSummary") is True
            nodes[uuid] = {
                "parent": row.get("parentUuid"),
                "role": role,
                "texts": texts,
                "compact": compact,
            }
            if visible and role in ("user", "assistant"):
                leaf = uuid
    return nodes, leaf


def _active_chain(nodes, leaf):
    chain = []
    seen = set()
    current = leaf
    while current and current not in seen:
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            return [], True
        chain.append(node)
        if node["compact"]:
            current = None
            break
        current = node.get("parent")
    if current in seen:
        return [], True
    chain.reverse()
    latest_summary = -1
    for index, node in enumerate(chain):
        if node["compact"]:
            latest_summary = index
    return (chain[latest_summary:] if latest_summary >= 0 else chain), False


def _middle_truncate(text, limit):
    if len(text) <= limit:
        return text
    omitted = "\n[... middle omitted by bounded context hook ...]\n"
    if limit <= len(omitted):
        return omitted[:limit]
    room = max(0, limit - len(omitted))
    before = room // 2
    return text[:before] + omitted + text[-(room - before):]


def _render(chain, limit=MAX_CONTEXT_CHARS):
    entries = []
    summary = None
    for node in chain:
        text = "\n".join(value.strip() for value in node["texts"] if value.strip())
        if not text:
            continue
        if node["compact"]:
            summary = "[LATEST COMPACTION SUMMARY]\n" + text
        else:
            label = "USER" if node["role"] == "user" else "ASSISTANT"
            entries.append(f"[{label}]\n{text}")

    header = (
        f"{MARKER}\n"
        "Filtered parent-session context. It is not evidence: verify material "
        "claims against the repository, reproducible results, or current "
        "authoritative sources. Thinking, tools, hook noise, and sidechains "
        "were excluded.\n"
    )
    footer = "\nEND_MAINFRAME_ADVISOR_CONTEXT"
    fixed = len(header) + len(footer) + 2
    if fixed >= limit:
        return header[:limit]

    selected = []
    remaining = limit - fixed
    if summary:
        kept_summary = _middle_truncate(summary, min(MAX_SUMMARY_CHARS, remaining))
        selected.append(kept_summary)
        remaining -= len(kept_summary) + 2

    newest = []
    for entry in reversed(entries):
        if remaining <= 0:
            break
        if len(entry) + 2 <= remaining:
            newest.append(entry)
            remaining -= len(entry) + 2
        else:
            newest.append(_middle_truncate(entry, remaining))
            remaining = 0
            break
    selected.extend(reversed(newest))
    if not selected:
        return f"{UNAVAILABLE}: no visible parent conversation was found."
    return header + "\n\n".join(selected) + footer


def build_context(path, limit=MAX_CONTEXT_CHARS):
    if not isinstance(path, str) or not path:
        return f"{UNAVAILABLE}: SubagentStart did not provide transcript_path."
    if not os.path.isfile(path):
        return f"{UNAVAILABLE}: the supplied parent transcript is not readable."
    offset = _latest_compaction_offset(path)
    nodes, leaf = _read_nodes(path, offset)
    chain, incomplete = _active_chain(nodes, leaf)
    # A rewind can append a new active branch after a compaction belonging to
    # the abandoned branch. Only then pay the cost of scanning the full file.
    if incomplete and offset:
        nodes, leaf = _read_nodes(path, 0)
        chain, incomplete = _active_chain(nodes, leaf)
    if not chain:
        return f"{UNAVAILABLE}: no active parent conversation was found."
    return _render(chain, limit)


def _hook_output(text):
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": text,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _bounded_hook_output(text, limit=MAX_HOOK_OUTPUT_CHARS):
    encoded = _hook_output(text)
    if len(encoded) <= limit:
        return encoded

    low = 0
    high = len(text)
    best = _hook_output("")
    while low <= high:
        middle = (low + high) // 2
        candidate = _hook_output(_middle_truncate(text, middle))
        if len(candidate) <= limit:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best


def main():
    payload = load_payload()
    if payload.get("hook_event_name") != "SubagentStart":
        return
    if payload.get("agent_type") != AGENT:
        return
    context = build_context(payload.get("transcript_path"))
    sys.stdout.write(_bounded_hook_output(context))


if __name__ == "__main__":
    run(main)
