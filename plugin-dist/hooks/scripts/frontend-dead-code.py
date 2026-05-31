#!/usr/bin/env python3
"""Stop hook: report dead files via Knip's `--include files` mode.

Opt-in per project: fires ONLY when a Knip config exists in the session cwd —
`knip.json`, `knip.ts`, `knip.js`, `knip.config.{js,ts,mjs,cjs}`, or a `knip`
key in `package.json`. If absent, exits silently.

Design:
- Dead-code reporting, NOT security. Knip with `--include files` finds source
  files that are never reached from any declared entry point. Files only,
  NOT unused exports — that mode has high FP on public-API entry points (per
  research synthesis + advisor curation).
- Stop-only. Knip scans the whole module graph; per-edit invocation would
  be too slow.
- Conditional: the hub does not ship a Knip config — entry points and
  project structure vary. User opts in by setting up Knip config; hub
  provides the runner.
- Decision: `additionalContext` (non-blocking), NOT `block`. Dead-file
  cleanup is housekeeping, not a contract violation — a blocking gate here
  would interrupt the workflow on every Stop with stale or transitional
  files. Per the hub principle "context cost must be justified" — block
  reserved for security / contract findings.
- Self-loop guard via `stop_hook_active`.
- Fail-safe: ANY error → exit 0 with no output. Missing knip → silent
  (install via install.sh `bootstrap_frontend_quality_tools`).
- Invocation: prefer local-PATH `knip`, fall back to `npx --yes knip@latest`.
- Stdlib only on Python side; shells out to `knip` / `npx`.
"""

import json
import os
import shutil
import subprocess
import sys

CONFIG_FILES = ("knip.json", "knip.jsonc", "knip.ts", "knip.js",
                "knip.config.js", "knip.config.ts", "knip.config.mjs",
                "knip.config.cjs")


def _has_config(cwd):
    for name in CONFIG_FILES:
        if os.path.isfile(os.path.join(cwd, name)):
            return True
    pkg = os.path.join(cwd, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "knip" in data:
                return True
        except Exception:
            return False
    return False


def _knip_cmd():
    binary = shutil.which("knip")
    if binary:
        return [binary]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "knip@latest"]
    return None


def _run(cwd):
    cmd = _knip_cmd()
    if cmd is None:
        return None
    args = cmd + ["--include", "files", "--reporter", "json"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              cwd=cwd, timeout=180)
    except Exception:
        return None
    if proc.returncode not in (0, 1, 2):
        return None
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return None
    issues = data.get("issues") or []
    paths = []
    for issue in issues:
        path = issue.get("file")
        if path:
            paths.append(path)
    return paths


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    cwd = payload.get("cwd") or "."
    if not _has_config(cwd):
        return
    dead_files = _run(cwd)
    if not dead_files:
        return

    lines = [f"  {p}" for p in dead_files[:15]]
    more = f"\n  …and {len(dead_files) - 15} more" if len(dead_files) > 15 else ""

    note = (
        f"frontend-dead-code: Knip flagged {len(dead_files)} unused source "
        f"file(s) (no entry-point path reaches them, per your project's Knip "
        f"config):\n" + "\n".join(lines) + more +
        "\nDelete if truly orphaned; if intentionally kept for a future entry "
        "point, add to the Knip config's `entry` array. Knip --include files "
        "mode reports FILES only (not unused exports — that mode has high FP "
        "on public-API surfaces). This is informational; you may proceed."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop", "additionalContext": note}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
