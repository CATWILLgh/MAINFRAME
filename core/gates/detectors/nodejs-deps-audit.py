#!/usr/bin/env python3
"""PostToolUse hook: scan Node.js dependency files for known CVEs via OSV-Scanner.

Reads the PostToolUse hook payload from stdin (JSON). Fires ONLY when the edit
touches `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, or
`bun.lock[b]` (sharp trigger, not per-edit on code files). Runs OSV-Scanner
against the file/dir and emits `additionalContext` with top CVE findings.

Design:
- Fires on dep-file changes only — zero overhead on regular .ts/.js edits.
- Authoritative source: OSV.dev database (Google + Linux Foundation + GitHub
  open source vulnerability format). Native multi-lockfile support means one
  tool covers npm / pnpm / yarn / bun ecosystems.
- OSV-Scanner invocation: `osv-scanner scan source --format=json --lockfile=<file>`
  for lockfiles; `scan source <dir>` when only `package.json` is touched (auto-
  detects sibling lockfile).
- Non-blocking: emits additionalContext only. The model decides whether to bump
  the affected packages.
- Fail-safe: ANY error -> exit 0 with no output. Missing osv-scanner -> install
  hint. Stdlib only on Python side; shells out to `osv-scanner`.
- Output cap: top 10 vulns to avoid token flood when a long-stale project has
  many CVEs.
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

LOCK_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb"}
MANIFEST_FILES = {"package.json"}


def _is_dep_file(file_path):
    base = os.path.basename(file_path)
    return base in LOCK_FILES or base in MANIFEST_FILES


def _is_lockfile(file_path):
    return os.path.basename(file_path) in LOCK_FILES


def _run_osv_scanner(file_path):
    """Return raw JSON dict from osv-scanner or sentinel string."""
    osv = shutil.which("osv-scanner")
    if not osv:
        return "OSV_MISSING"
    if _is_lockfile(file_path):
        args = [osv, "scan", "source", "--format=json", "--lockfile=" + file_path]
    else:
        args = [osv, "scan", "source", "--format=json", os.path.dirname(file_path) or "."]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if proc.returncode not in (0, 1):
        return None
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return None


def _extract_vulns(audit_result):
    """Flatten OSV output → list of (pkg, version, vuln_id, summary)."""
    vulns = []
    for r in (audit_result or {}).get("results", []):
        for pkg in r.get("packages", []):
            name = pkg.get("package", {}).get("name", "?")
            version = pkg.get("package", {}).get("version", "?")
            for v in pkg.get("vulnerabilities", []) or []:
                vid = v.get("id", "?")
                summary = (v.get("summary") or v.get("details") or "").strip().splitlines()[0]
                vulns.append((name, version, vid, summary))
    return vulns


def main():
    payload = load_payload()
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or not _is_dep_file(file_path):
        return
    if not os.path.exists(file_path):
        return

    result = _run_osv_scanner(file_path)
    if result is None:
        return
    if result == "OSV_MISSING":
        note = (
            "nodejs-deps-audit: `osv-scanner` is not installed; Node dependency "
            "CVE scanning is OFF. Install the binary from "
            "https://github.com/google/osv-scanner/releases (or via `go install "
            "github.com/google/osv-scanner/v2/cmd/osv-scanner@latest`) for "
            "known-vulnerability detection against the OSV.dev database when "
            "dependency files change."
        )
        emit_note("PostToolUse", note)
        return

    vulns = _extract_vulns(result)
    if not vulns:
        return

    lines = []
    for name, version, vid, summary in vulns[:10]:
        suffix = f" — {summary[:100]}" if summary else ""
        lines.append(f"  {name}@{version}: {vid}{suffix}")
    more = f"\n  …and {len(vulns) - 10} more" if len(vulns) > 10 else ""

    note = (
        f"nodejs-deps-audit: {len(vulns)} known CVE(s) in dependencies "
        f"declared by {file_path}:\n" + "\n".join(lines) + more +
        "\nSource: OSV.dev database (osv-scanner). Bump the affected packages "
        "to a fixed version, or surface via `surface-ticket` if the upgrade is "
        "out of scope for the current task."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
