#!/usr/bin/env python3
"""Stop hook: hard gate against unresolved suppression markers / debug residue.

Fires when Claude is about to stop a turn. If the working-tree diff vs `git HEAD`
contains newly-added suppression / placeholder markers or debug residue
(`debugger`, `breakpoint()`, `pdb.set_trace`, `var_dump`/`dd`, `console.debug`)
in source-code files, block the stop with a reason — forcing resolution (or
explicit user permission) before the turn is declared done.

Only ADDED (`+`) lines are flagged, so legacy markers from prior commits don't
trip it. Shared scaffolding is in `_hooklib`, the detector sets in `_markers`.
Self-loop-guarded; fail-open on git/lib failure (any error -> exit 0).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import added_lines_by_file, emit_block, load_payload, run, stop_guard_cwd
    from _markers import MARKERS, DEBUG_RESIDUE
except Exception:
    sys.exit(0)


def _added_markers_in_diff(cwd):
    """Sorted labels of markers / debug residue in added (`+`) lines of the
    working-tree diff vs HEAD. Empty if none, or if git is unavailable."""
    found = set()
    for file_ext, body in added_lines_by_file(cwd):
        for label, rx in MARKERS:
            if rx.search(body):
                found.add(label)
        for label, rx, exts in DEBUG_RESIDUE:
            if file_ext in exts and rx.search(body):
                found.add(label)
    return sorted(found)


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return  # already blocked once this turn -> let the stop through
    labels = _added_markers_in_diff(cwd)
    if not labels:
        return  # nothing found, or git unavailable -> let Claude stop
    reason = (
        "Suppression markers or debug residue are present in the working-tree "
        f"diff vs HEAD: {', '.join(labels)}. Per the global engineering rules "
        "these are not allowed in work declared complete — suppression markers "
        "need explicit user permission, debug residue must be removed. Resolve "
        "them in the affected source files (or obtain explicit user permission "
        "to keep a marker) before stopping the turn."
    )
    emit_block(reason)


if __name__ == "__main__":
    run(main)
