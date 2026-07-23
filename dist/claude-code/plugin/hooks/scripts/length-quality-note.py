#!/usr/bin/env python3
"""Stop hook: advisory note when a changed file or Python function exceeds
CLAUDE.md's length rule ("files under 400 lines, functions under 60
lines").

Design (decision-reviewer + advisor, 2026-07-06): no before/after size
comparison, unlike the security delta/inherited split -- at advisory-only
severity the split's one benefit (nagging on an already-ticketed file only if
it got worse) doesn't earn its cost (per-file git spawns, an incoherent
`ast.walk` qualname match across versions, rename false-positives). Instead:
flag any current violation; suppress per file when a ticket under
docs/tickets/ names it (uniform, no delta exception) -- ticket-discipline
alone is the noise-reduction mechanism, same principle as the security gates.

Stop-only (no PostToolUse twin): without a delta split, a PostToolUse
reminder would repeat identically on every edit to an already-long file with
no state to dedup it -- the closest precedent for a non-blocking quality
metric, `fallow-quality-note.py`, is Stop-only for the same reason.

File-length applies to `_length_check.FILE_LENGTH_EXTENSIONS` (excludes
.sql/.vue/.svelte -- see that module for why). Function-length is Python-only
(`ast`-based); a `SyntaxError` on malformed Python skips the function check
for that file only, the file-length check still runs. Files whose comment
headers identify them as machine-generated are skipped by both checks.

Never blocks (user decision 2026-07-06): only `emit_note`, matching
`fallow-quality-note.py`'s severity, never `emit_block`. No throttle: unlike
`fallow-quality-note` (throttled because it shells out to an expensive
external analyzer), this is pure local line-counting + `ast.parse` -- cost is
comparable to the un-throttled `python-security-stop-gate.py`.
Fail-safe: any error -> exit 0, no output.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (changed_files, emit_note, ext, load_payload, run,
                          stop_guard_cwd, tickets_mentioning)
    from _length_check import (FILE_LENGTH_EXTENSIONS, FILE_LENGTH_THRESHOLD,
                               FUNCTION_LENGTH_THRESHOLD, count_lines,
                               is_machine_generated, over_threshold_functions)
except Exception:
    sys.exit(0)

FUNC_EXTS = (".py", ".pyi")
MAX_LISTED = 5


def _untracked_files(cwd, exts):
    """Absolute paths of untracked files in `cwd`, filtered to `exts`.

    `changed_files` (`git diff HEAD`) never sees untracked files -- git diff
    only compares tracked/staged content against HEAD, so a freshly
    Write-created file (never `git add`-ed) is invisible to it. This is the
    hook's primary scenario -- a brand-new over-threshold file -- so it must
    be enumerated separately via `git ls-files --others`.
    """
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="replace")
    except Exception:
        return []
    files = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel or ext(rel) not in exts:
            continue
        abs_path = os.path.join(cwd, rel)
        if os.path.exists(abs_path):
            files.append(abs_path)
    return files


def _scan(cwd):
    """(file_over, func_over) for human-maintained, unticketed changed files.

    file_over: [(path, line_count)]. func_over: [(path, qualname, start, length)].
    Ticketed and machine-generated files are skipped entirely -- suppression is
    uniform, per file, for both checks.
    """
    file_over, func_over = [], []
    candidates = set(changed_files(cwd, FILE_LENGTH_EXTENSIONS))
    candidates.update(_untracked_files(cwd, FILE_LENGTH_EXTENSIONS))
    for path in sorted(candidates):
        if tickets_mentioning(cwd, path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        if is_machine_generated(text):
            continue
        n = count_lines(text)
        if n > FILE_LENGTH_THRESHOLD:
            file_over.append((path, n))
        if ext(path) in FUNC_EXTS:
            try:
                findings = over_threshold_functions(text)
            except SyntaxError:
                findings = []
            for qualname, start, _end, length in findings:
                func_over.append((path, qualname, start, length))
    return file_over, func_over


def _format_note(file_over, func_over):
    parts = []
    if file_over:
        shown = file_over[:MAX_LISTED]
        lines = [f"  - {p} ({n} lines)" for p, n in shown]
        more = (f"\n  …and {len(file_over) - MAX_LISTED} more"
                if len(file_over) > MAX_LISTED else "")
        parts.append(
            f"{len(file_over)} file(s) over {FILE_LENGTH_THRESHOLD} lines:\n"
            + "\n".join(lines) + more)
    if func_over:
        shown = func_over[:MAX_LISTED]
        lines = [f"  - {p}:{s} `{q}` ({n} lines)" for p, q, s, n in shown]
        more = (f"\n  …and {len(func_over) - MAX_LISTED} more"
                if len(func_over) > MAX_LISTED else "")
        parts.append(
            f"{len(func_over)} function(s) over {FUNCTION_LENGTH_THRESHOLD} "
            "lines:\n" + "\n".join(lines) + more)
    return (
        "length-quality-note (advisory): CLAUDE.md's length rule "
        "(\"files under 400 lines, functions under 60 lines\") flags:\n\n"
        + "\n\n".join(parts) +
        "\n\nNo ticket currently names these files. This is a reminder, not "
        "a block — split the file / extract the function if it fits this "
        "task's scope, or create/update a ticket via the `surface-ticket` "
        "skill."
    )


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    file_over, func_over = _scan(cwd)
    if not file_over and not func_over:
        return
    emit_note("Stop", _format_note(file_over, func_over))


if __name__ == "__main__":
    run(main)
