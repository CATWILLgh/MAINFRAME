#!/usr/bin/env python3
"""Stop hook: hard gate against unresolved Python security findings.

Fires when Claude is about to stop a turn. Collects .py files modified in the
session's working-tree diff vs `git HEAD`, runs Ruff's curated S-rule subset
on the union, and blocks the stop with a reason if any findings remain.

Design mirrors `stop-gate-suppression-markers.py`:
- Block via `{"decision": "block", "reason": ...}` on stdout, exit 0.
- Self-loop guard: if `stop_hook_active` is true on input, exit 0 silently.
- Diff-aware file selection: only files touched in this session (via
  `git diff HEAD --name-only`). Pre-existing security findings in untouched
  files are not the agent's job to fix here.
- Ruff is the analyzer: full-file scan with the same curated subset as
  `python-security-scan.py` (PostToolUse). `--ignore-noqa` — silenced markers
  do not buy past this gate.
- Fail-safe: any error -> exit 0 without output. Gate must never break a
  session because of itself. Missing ruff -> exit 0 (PostToolUse already
  surfaced the install hint once).
- Stdlib only on the Python side; shells out to `git` and `ruff`.
"""

import json
import os
import shutil
import subprocess
import sys

CURATED_RULES = (
    "S102,S307,S301,S506,S602,S604,S501,S324,S311,S105,S106,S107,"
    "B006,B008,B011,B904"
)
PY_EXTS = (".py", ".pyi")


def _ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def _changed_py_files(cwd):
    """Return absolute paths of .py files modified in the working tree vs HEAD."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "HEAD", "--name-only", "--diff-filter=AM"],
            cwd=cwd, stderr=subprocess.DEVNULL, timeout=5,
        ).decode(errors="replace")
    except Exception:
        return []
    files = []
    for rel in out.splitlines():
        rel = rel.strip()
        if not rel or _ext(rel) not in PY_EXTS:
            continue
        abs_path = os.path.join(cwd, rel)
        if os.path.exists(abs_path):
            files.append(abs_path)
    return files


def _run_ruff(files):
    ruff = shutil.which("ruff")
    if not ruff or not files:
        return []
    try:
        proc = subprocess.run(
            [ruff, "check", "--select", CURATED_RULES, "--output-format", "json",
             "--no-cache", "--ignore-noqa", "--force-exclude", *files],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return []
    if proc.returncode not in (0, 1):
        return []
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        return []


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    cwd = payload.get("cwd") or "."
    files = _changed_py_files(cwd)
    if not files:
        return
    findings = _run_ruff(files)
    if not findings:
        return

    lines = []
    for f in findings[:15]:
        code = f.get("code", "?")
        fn = f.get("filename") or "?"
        ln = (f.get("location") or {}).get("row", "?")
        msg = (f.get("message") or "").strip()
        lines.append(f"  {fn}:{ln} — {code}: {msg}")
    more = f"\n  …and {len(findings) - 15} more" if len(findings) > 15 else ""

    reason = (
        f"python-security-stop-gate: {len(findings)} unresolved finding(s) "
        f"in this session's modified .py files:\n" +
        "\n".join(lines) + more +
        "\nThese are OWASP/Bandit-aligned dangerous patterns (S-rules) and "
        "zero-FP correctness bugs (B-rules) via Ruff curated subset. Resolve "
        "before declaring the turn done. If a finding is a genuine exception "
        "(rare), surface via the `surface-ticket` skill — `# noqa` is not "
        "honored by this gate."
    )
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
