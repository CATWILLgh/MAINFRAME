#!/usr/bin/env python3
"""Block completion on unresolved residue introduced by this session."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (
        emit_block, ext, load_payload, log_hook_signal, run, stop_guard_cwd,
    )
    from _markers import marker_counts
    from _marker_state import unresolved
except Exception:
    sys.exit(0)


_MAX_LOCATIONS = 6


def _display_path(file_path, cwd):
    path = os.path.realpath(file_path)
    base = os.path.realpath(cwd or ".")
    try:
        if os.path.commonpath((base, path)) == base:
            return os.path.relpath(path, base)
    except (OSError, ValueError):
        pass
    return os.path.basename(path)


def _current_findings(details, cwd):
    rows = []
    total = 0
    for path, baselines in details.items():
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                current = marker_counts(handle.read(), ext(path), path)
        except (FileNotFoundError, OSError):
            continue
        name = _display_path(path, cwd)
        for label, baseline in baselines.items():
            owned = max(0, current.get(label, 0) - int(baseline))
            if not owned:
                continue
            total += owned
            suffix = "s" if owned != 1 else ""
            rows.append(f"{name}: {label} ({owned} occurrence{suffix})")
    return rows, total


def main():
    payload = load_payload()
    if stop_guard_cwd(payload) is None:
        return
    session_id = payload.get("session_id")
    if not session_id:
        raise ValueError("marker stop gate requires session_id")
    agent_id = payload.get("agent_id")
    details = unresolved(
        session_id, agent_id,
        include_subagents=not bool(agent_id),
        include_details=True,
    )
    if not details:
        return
    findings, count = _current_findings(details, payload.get("cwd"))
    if not count:
        return
    suffix = "s" if count != 1 else ""
    verb = "remain" if count != 1 else "remains"
    locations = "".join(
        f"  - {row}\n" for row in findings[:_MAX_LOCATIONS]
    )
    if len(findings) > _MAX_LOCATIONS:
        locations += f"  - ... {len(findings) - _MAX_LOCATIONS} more locations\n"
    reason = (
        f"{count} unfinished-code or diagnostic finding{suffix} introduced by "
        f"this session {verb}:\n" + locations +
        "Complete the underlying behavior and its relevant verification before "
        "stopping. Do not merely remove a marker when it identifies work required "
        "by the current task. If it annotated an unrelated observation, revert "
        "that annotation and record the observation through the repository ticket "
        "workflow without expanding the current scope."
    )
    emitted_reason = emit_block(reason)
    log_hook_signal(
        __file__, "unfinished-residue", "blocked", count, payload,
        context=emitted_reason,
    )


if __name__ == "__main__":
    run(main)
