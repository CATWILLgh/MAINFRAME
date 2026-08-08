#!/usr/bin/env python3
"""PostToolUse hook: scan Python dependency files for known CVEs via pip-audit.

Reads the PostToolUse hook payload from stdin (JSON). Fires ONLY when the edit
touches `pyproject.toml`, `requirements*.txt`, `Pipfile`, or `setup.py` (rare
sharp trigger, not per-edit). Runs `pip-audit` against the file or the project
state and emits `additionalContext` with top CVE findings.

Design:
- Fires on dep-file changes only — zero overhead on regular Python edits.
- Authoritative source: PyPA Advisory Database (official, curated, low-FP by
  definition — a CVE is a CVE; whether exploitable in user's context is
  context-dependent, but the finding itself is not noise).
- pip-audit invocation: `pip-audit --format json --strict` against the project
  root (auto-detects pyproject/requirements). For `requirements.txt` edits
  explicitly: `pip-audit --requirement <file> --format json`.
- Non-blocking: emits additionalContext only. The model decides whether to
  pin/upgrade the affected packages.
- Fail-safe: ANY error -> exit 0 with no output (consistent with the existing
  hub hook precedent). Missing pip-audit -> one-line install hint.
- Output cap: top 10 critical/high findings to avoid token flood when a
  long-stale project has many CVEs.
- Stdlib only on the Python side; shells out to `pip-audit`.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import load_payload, emit_note, run
except Exception:
    sys.exit(0)

DEP_FILES = {"pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "setup.cfg"}
DEP_FILE_PREFIXES = ("requirements",)


def _is_dep_file(file_path):
    base = os.path.basename(file_path)
    if base in DEP_FILES:
        return True
    if base.startswith(DEP_FILE_PREFIXES) and base.endswith(".txt"):
        return True
    return False


def _run_pip_audit(file_path):
    """Run pip-audit. Return list of vuln dicts or sentinel string."""
    audit = shutil.which("pip-audit")
    if not audit:
        return "AUDIT_MISSING"
    project_root = os.path.dirname(file_path) or "."
    base = os.path.basename(file_path)
    args = [audit, "--format", "json", "--progress-spinner", "off"]
    if base.startswith("requirements") and base.endswith(".txt"):
        args += ["--requirement", file_path]
    else:
        args += ["--strict"]
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=60, cwd=project_root,
        )
    except Exception:
        return None
    if proc.returncode not in (0, 1):
        return None
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return None


def _extract_vulns(audit_result):
    """Flatten pip-audit JSON output into list of (package, version, vuln_id, fix)."""
    vulns = []
    if isinstance(audit_result, dict):
        deps = audit_result.get("dependencies", [])
    elif isinstance(audit_result, list):
        deps = audit_result
    else:
        return []
    for dep in deps:
        name = dep.get("name") or dep.get("package", "?")
        version = dep.get("version", "?")
        for v in dep.get("vulns", []) or []:
            vid = v.get("id", "?")
            fix = ", ".join(v.get("fix_versions") or []) or "no fix listed"
            description = (v.get("description") or "").strip().splitlines()[0] if v.get("description") else ""
            vulns.append((name, version, vid, fix, description))
    return vulns


def main():
    payload = load_payload()
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_dep_file(file_path):
        return
    if not os.path.exists(file_path):
        return

    result = _run_pip_audit(file_path)
    if result is None:
        return
    if result == "AUDIT_MISSING":
        note = (
            "python-deps-audit: `pip-audit` is not installed; dependency CVE "
            "scanning is OFF. Install via `uv tool install pip-audit` (or "
            "`pipx install pip-audit`) for known-vulnerability detection "
            "against the PyPA Advisory Database when dependency files change."
        )
        emit_note("PostToolUse", note)
        return

    vulns = _extract_vulns(result)
    if not vulns:
        return

    lines = []
    for name, version, vid, fix, desc in vulns[:10]:
        suffix = f" — {desc[:100]}" if desc else ""
        lines.append(f"  {name}=={version}: {vid} (fix: {fix}){suffix}")
    more = f"\n  …and {len(vulns) - 10} more" if len(vulns) > 10 else ""

    note = (
        f"python-deps-audit: {len(vulns)} known CVE(s) in dependencies "
        f"declared by {file_path}:\n" + "\n".join(lines) + more +
        "\nSource: PyPA Advisory Database (pip-audit). Bump affected packages "
        "to the listed fix versions, or surface via `surface-ticket` if the "
        "upgrade is out of scope for the current task."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
