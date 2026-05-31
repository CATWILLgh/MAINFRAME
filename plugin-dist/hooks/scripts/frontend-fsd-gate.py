#!/usr/bin/env python3
"""Stop hook: enforce FSD architectural layer rules via dependency-cruiser.

Opt-in per project: fires ONLY when `.dependency-cruiser.{cjs,js,json}` exists
in the session cwd. If absent, exits silently — the hub does not impose FSD
on projects that did not opt in.

Design:
- Architecture enforcement, NOT security. Catches upward-direction imports
  forbidden by FSD: entities → features/pages/widgets, shared → entities,
  features → pages, etc. Per https://feature-sliced.design.
- Stop-only. Dependency-cruiser scans the whole import graph; per-edit
  invocation would be too slow for interactive UX (research agent reported
  CI-suitable, not per-edit).
- Conditional: the hub does not ship a FSD rule config — project rules vary
  (alias prefix, monorepo path layout, source dir). User opts in by setting
  up `.dependency-cruiser.cjs` (or .js/.json) with their FSD rules. Hub
  provides the runner; user provides the policy.
- Self-loop guard via `stop_hook_active`.
- Block via `{"decision": "block", "reason": ...}` on findings.
- Fail-safe: ANY error → exit 0 with no output. Missing dependency-cruiser →
  silent (install via install.sh `bootstrap_frontend_quality_tools`).
- Invocation: prefer local-PATH `depcruise`, fall back to `npx --yes
  dependency-cruiser@latest`.
- Stdlib only on Python side; shells out to `depcruise` / `npx`.

Why not a per-project hard-coded ruleset shipped by the hub: project layouts
diverge (alias prefix `@/` vs `~/`, monorepo `apps/X/src/` vs flat `src/`,
custom layer names). A one-size-fits-all hub-shipped config would FP on most
real projects. Opt-in via user-defined config = zero noise where unwanted,
real signal where wanted. Per advisor discipline: "Conditional on
context, not blanket."
"""

import json
import os
import shutil
import subprocess
import sys

CONFIG_FILES = (".dependency-cruiser.cjs", ".dependency-cruiser.js",
                ".dependency-cruiser.json", "dependency-cruiser.config.cjs",
                "dependency-cruiser.config.js", "dependency-cruiser.config.mjs")
SCAN_GLOB_DEFAULT = "src"


def _has_config(cwd):
    for name in CONFIG_FILES:
        if os.path.isfile(os.path.join(cwd, name)):
            return True
    return False


def _depcruise_cmd():
    binary = shutil.which("depcruise")
    if binary:
        return [binary]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "dependency-cruiser@latest"]
    return None


def _run(cwd):
    cmd = _depcruise_cmd()
    if cmd is None:
        return None
    args = cmd + ["--output-type", "json", SCAN_GLOB_DEFAULT]
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              cwd=cwd, timeout=120)
    except Exception:
        return None
    if proc.returncode not in (0, 1, 2, 3, 4):
        return None
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return None
    summary = data.get("summary") or {}
    return summary.get("violations", []) or []


def main():
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    cwd = payload.get("cwd") or "."
    if not _has_config(cwd):
        return
    violations = _run(cwd)
    if not violations:
        return

    lines = []
    for v in violations[:15]:
        rule = (v.get("rule") or {}).get("name", "?")
        frm = v.get("from", "?")
        to = v.get("to", "?")
        lines.append(f"  {rule}: {frm} → {to}")
    more = f"\n  …and {len(violations) - 15} more" if len(violations) > 15 else ""

    reason = (
        f"frontend-fsd-gate: dependency-cruiser flagged {len(violations)} "
        f"architectural rule violation(s) (per your project's "
        f".dependency-cruiser config):\n" + "\n".join(lines) + more +
        "\nFix the dependency direction (typically Feature-Sliced Design: lower "
        "layers cannot import from upper layers). If a violation is a genuine "
        "exception, either add a precise allow-rule in the project config or "
        "surface via the `surface-ticket` skill — this gate honors only the "
        "project config, not inline suppressions."
    )
    print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
