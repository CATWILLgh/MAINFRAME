#!/usr/bin/env python3
"""Stop hook: advisory code-quality note from `fallow` for TS/JS projects.

Runs the local `fallow` analyzer (dead files, circular imports, architecture
boundaries, complexity, duplication) when the working tree has changed TS/JS
files, and surfaces a CONSERVATIVE subset as a non-blocking note. Categories
proven noisy in the 2026-06-11 pilot are never reported: dependency flags
(string-referenced runtime deps) and unused exports (test-only consumers are
missed by the analyzer). Each emitted note logs an `incident` telemetry row per
category so precision is measurable before any promotion to a blocking gate.

Throttled to one run per project per THROTTLE_SECONDS (whole-repo analysis,
~2s on a mid-size Next.js app). Silent when `fallow` is not installed, the cwd
is not a git repo, or nothing significant is found. Fail-safe: any error ->
exit 0.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (changed_files, emit_note, load_payload, log_event,
                          run, stop_guard_cwd)
except Exception:
    sys.exit(0)

JS_EXTS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
                     ".vue", ".svelte"})
THROTTLE_SECONDS = 300
ANALYZE_TIMEOUT = 30
CLONE_GROUPS_MIN = 20
MAX_LISTED = 5
_SKIP_UNUSED = ("docs/", ".test.", ".spec.", "__tests__/", "/tests/")


def _throttled(cwd, stamp_dir=None):
    """True when this project ran within the window; stamps the run otherwise."""
    d = stamp_dir or tempfile.gettempdir()
    key = hashlib.sha256(cwd.encode("utf-8", "replace")).hexdigest()[:16]
    stamp = os.path.join(d, f"fallow-note-{key}.stamp")
    try:
        if time.time() - os.path.getmtime(stamp) < THROTTLE_SECONDS:
            return True
    except OSError:
        pass
    try:
        with open(stamp, "w") as fh:
            fh.write(str(int(time.time())))
    except OSError:
        pass
    return False


def _keep_unused(path):
    probe = "/" + path.lstrip("/")
    return path and not any(s in probe for s in _SKIP_UNUSED)


def build_note(report):
    """(note_text, per-category counts) from a fallow combined report, or
    (None, {}) when nothing crosses the conservative thresholds."""
    if not isinstance(report, dict):
        return None, {}
    check = report.get("check") or {}
    health = report.get("health") or {}
    dupes = (report.get("dupes") or {}).get("stats") or {}
    if not isinstance(check, dict) or not isinstance(health, dict):
        return None, {}

    cycles = check.get("circular_dependencies") or []
    bounds = ((check.get("boundary_violations") or [])
              + (check.get("boundary_call_violations") or []))
    unused = [it.get("path", "") for it in (check.get("unused_files") or [])
              if _keep_unused(it.get("path", ""))]
    critical = [f for f in (health.get("findings") or [])
                if isinstance(f, dict) and f.get("severity") == "critical"]
    clone_groups = dupes.get("clone_groups") or 0

    significant_clones = clone_groups >= CLONE_GROUPS_MIN
    if not (cycles or bounds or unused or critical or significant_clones):
        return None, {}

    lines = []
    if cycles:
        first = " -> ".join((cycles[0].get("files") or [])[:3])
        lines.append(f"  - {len(cycles)} circular import(s), e.g. {first}")
    if bounds:
        lines.append(f"  - {len(bounds)} architecture boundary violation(s)")
    if unused:
        shown = ", ".join(unused[:MAX_LISTED])
        more = f" (+{len(unused) - MAX_LISTED} more)" if len(unused) > MAX_LISTED else ""
        lines.append(f"  - {len(unused)} unused source file(s): {shown}{more}")
    if critical:
        worst = max(critical, key=lambda f: f.get("cyclomatic") or 0)
        lines.append(
            f"  - {len(critical)} critically complex function(s); worst: "
            f"`{worst.get('name', '?')}` in {worst.get('path', '?')} "
            f"({worst.get('line_count', '?')} lines, "
            f"cyclomatic {worst.get('cyclomatic', '?')})")
    if significant_clones:
        pct = dupes.get("duplication_percentage")
        pct_part = f", {pct}% of code" if pct is not None else ""
        lines.append(f"  - duplication: {clone_groups} clone groups{pct_part}")

    note = (
        "fallow code-quality note (advisory): this project's TS/JS changed and "
        "the analyzer reports:\n" + "\n".join(lines) + "\n"
        "Address what falls into the current task's scope; the rest belongs in "
        "tickets, not silent walk-past. This is a reminder, not a block."
    )
    counts = {"cycles": len(cycles), "boundaries": len(bounds),
              "unused_files": len(unused), "critical": len(critical),
              "clone_groups": clone_groups}
    return note, counts


def _analyze(cwd):
    exe = shutil.which("fallow")
    if not exe:
        return None
    proc = subprocess.run([exe, "--root", cwd, "--format", "json"],
                          capture_output=True, text=True,
                          timeout=ANALYZE_TIMEOUT)
    raw = proc.stdout or ""
    start = raw.find("{")
    if start < 0:
        return None
    return json.loads(raw[start:])


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    if not changed_files(cwd, JS_EXTS):
        return
    if _throttled(cwd):
        return
    report = _analyze(cwd)
    if not report:
        return
    note, counts = build_note(report)
    if not note:
        return
    emit_note("Stop", note)
    log_event("incident", dict({"hook": "fallow-quality-note",
                                "rule_id": "fallow"}, **counts), payload)


if __name__ == "__main__":
    run(main)
