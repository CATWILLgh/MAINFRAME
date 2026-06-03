#!/usr/bin/env python3
"""Stop hook: hard gate against unresolved Node/TS security findings via Semgrep.

Fires when Claude is about to stop a turn. Collects .ts/.tsx/.js/.jsx/.mjs/.cjs
files modified in the session's working-tree diff vs `git HEAD`, runs Semgrep's
`p/security-audit` ruleset on the union, and blocks the stop with a reason if
any findings remain.

Design (honestly framed — NOT a mirror of Python's ruff-fast per-edit + Stop combo):
- Stop-only, not PostToolUse. Semgrep is a Python tool with multi-second
  warm-run cost (~3s for typical session diff in probe). Per-edit invocation
  would break interactive UX. Stop-time is the correct timing budget for it.
- Semgrep `p/security-audit` ruleset chosen empirically over `p/default` (same
  coverage in our probe, slightly tighter focus). Coverage is CONSERVATIVE,
  NOT zero-FP: Semgrep is a security-review tool tuned for low-FP triage,
  high-confidence patterns only. Probe caught child_process injection from a
  3-pattern bad-code corpus (eval / md5 / child_process). Frame this honestly
  to the model — finding ABSENCE is not a clean bill of health.
- Hub-shipped rule `frontend-token-storage.yml` adds the
  localStorage / sessionStorage token-storage check that the public ruleset
  does not cover. Lives next to this script under `rules/`, located via
  `os.path.realpath(__file__)` so the symlinked deployment still finds it.
- Self-loop guard: if `stop_hook_active` is true on input, exit 0 silently
  (prevents the gate from blocking forever once Claude is mid-cleanup).
- Block via `{"decision": "block", "reason": ...}` on stdout, exit 0.
- Fail-safe: any error -> exit 0 without output. Missing semgrep -> silent
  (PostToolUse layer would have surfaced install hint already if it had a
  corresponding install reminder — for Node v1 there is no per-edit code
  scanner, so install state is surfaced only by install.sh once).
- Stdlib only on Python side; shells out to `git` and `semgrep`.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import changed_files, emit_block, load_payload, run, stop_guard_cwd
except Exception:
    sys.exit(0)

SEMGREP_CONFIGS = ["p/security-audit"]
JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

_HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
_HUB_RULES_DIR = os.path.join(_HOOKS_DIR, "rules")


def _hub_rule_configs():
    if not os.path.isdir(_HUB_RULES_DIR):
        return []
    out = []
    for name in sorted(os.listdir(_HUB_RULES_DIR)):
        if name.endswith((".yml", ".yaml")):
            out.append(os.path.join(_HUB_RULES_DIR, name))
    return out


def _run_semgrep(files):
    semgrep = shutil.which("semgrep")
    if not semgrep or not files:
        return []
    configs = list(SEMGREP_CONFIGS) + _hub_rule_configs()
    args = [semgrep, "scan", "--json", "--quiet", "--no-git-ignore"]
    for c in configs:
        args.extend(["--config", c])
    args.extend(files)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except Exception:
        return []
    if proc.returncode not in (0, 1):
        return []
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return []
    return data.get("results", []) or []


def main():
    payload = load_payload()
    cwd = stop_guard_cwd(payload)
    if cwd is None:
        return
    files = changed_files(cwd, JS_EXTS)
    if not files:
        return
    findings = _run_semgrep(files)
    if not findings:
        return

    lines = []
    for f in findings[:15]:
        code = f.get("check_id", "?").split(".")[-1]
        path = f.get("path", "?")
        ln = (f.get("start") or {}).get("line", "?")
        msg = ((f.get("extra") or {}).get("message") or "").strip()[:120]
        lines.append(f"  {path}:{ln} — {code}: {msg}")
    more = f"\n  …and {len(findings) - 15} more" if len(findings) > 15 else ""

    reason = (
        f"nodejs-security-stop-gate: Semgrep flagged {len(findings)} "
        f"security finding(s) in this session's modified .ts/.js files:\n" +
        "\n".join(lines) + more +
        "\nSources: Semgrep `p/security-audit` ruleset (high-confidence low-FP "
        "patterns, NOT zero-FP wholesale OWASP — finding absence is not a clean "
        "bill of health) + hub `frontend-token-storage.yml` (localStorage / "
        "sessionStorage token-storage XSS exposure, per OWASP DOM-based XSS "
        "Prevention). Resolve before declaring done. If a finding is a genuine "
        "exception, surface via the `surface-ticket` skill — Semgrep does not "
        "honor inline suppression markers in this gate."
    )
    emit_block(reason)


if __name__ == "__main__":
    run(main)
