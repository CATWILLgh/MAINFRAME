#!/usr/bin/env python3
"""PostToolUse hook: scan freshly-written/edited Python files for high-confidence
OWASP-aligned dangerous patterns AND zero-FP correctness bugs, via Ruff's
curated S (flake8-bandit) + B (flake8-bugbear) rule subsets.

Reads the PostToolUse hook payload from stdin (JSON), filters to .py edits,
runs `ruff check --select <subset> --output-format json` on the file, and emits
a non-blocking `additionalContext` note with the findings.

Design:
- Curated subset (not `--select S` wholesale): S-rules — S102 exec, S307 eval,
  S301 pickle.load, S506 unsafe yaml.load, S602/S603/S604 subprocess shell=True,
  S501 requests verify=False, S324 insecure hash (md5/sha1), S311 random for
  crypto, S105/S106/S107 hardcoded password literals. B-rules (zero-FP
  correctness bugs) — B006 mutable default arg, B008 function call as default,
  B011 assert False (stripped by python -O), B904 raise without from in except
  (loses traceback chain). Sources: Bandit catalog (PyCQA) ported in Ruff under
  S-prefix, flake8-bugbear under B-prefix (docs.astral.sh/ruff/rules/).
  Curation matters — wholesale `--select S` includes S101 which fires on every
  pytest `assert`, training the agent to ignore the hook (advisor 2026-05-30).
  Deliberately excluded from B: B007 (unused loop var — legitimate with `_`),
  B017 (assert raises broad Exception — test style not bug), and SIM/PERF/PIE
  (stylistic opinions, not real bugs).
- Inline `# noqa: S<id>` is NOT honored: this hook passes
  `--no-cache --ignore-noqa` to ruff. Genuine exceptions surface via the
  `surface-ticket` skill, not silenced markers — keeps `no-suppression-markers`
  hub rule coherent.
- Non-blocking: PostToolUse cannot block; only emits additionalContext.
- Fail-safe: ANY error -> exit 0 with no output (consistent with the existing
  hub hook precedent). Hook must never break or noise-up a session.
- Stdlib only: no venv, no third-party Python deps. The hook DOES shell out
  to `ruff`; if ruff is absent the hook surfaces a single install hint.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, ext, load_payload, run
except Exception:
    sys.exit(0)

CURATED_RULES = (
    "S102,S307,S301,S506,S602,S604,S501,S324,S311,S105,S106,S107,"
    "B006,B008,B011,B904"
)
PY_EXTS = (".py", ".pyi")

RULE_LABELS = {
    "S102": "exec()",
    "S307": "eval()",
    "S301": "pickle.load (RCE on untrusted input)",
    "S506": "yaml.load without SafeLoader",
    "S602": "subprocess call with shell=True",
    "S604": "function call with shell=True",
    "S501": "request verify=False (TLS disabled)",
    "S324": "insecure hash (md5/sha1) for security purpose",
    "S311": "random module for crypto/security",
    "S105": "possible hardcoded password (string literal)",
    "S106": "possible hardcoded password (func arg)",
    "S107": "possible hardcoded password (default arg)",
    "B006": "mutable default arg (persists across calls)",
    "B008": "function call as default arg (evaluated at def time)",
    "B011": "assert False (stripped by python -O; use raise)",
    "B904": "raise without `from` in except (loses traceback chain)",
}


def _run_ruff(file_path):
    """Run ruff S-subset on `file_path`. Return list of finding dicts or None."""
    ruff = shutil.which("ruff")
    if not ruff:
        return "RUFF_MISSING"
    try:
        proc = subprocess.run(
            [ruff, "check", "--select", CURATED_RULES, "--output-format", "json",
             "--no-cache", "--ignore-noqa", "--force-exclude", file_path],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    if proc.returncode not in (0, 1):
        return None
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        return None


def main():
    payload = load_payload()
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or ext(file_path) not in PY_EXTS:
        return
    if not os.path.exists(file_path):
        return

    findings = _run_ruff(file_path)
    if findings is None:
        return
    if findings == "RUFF_MISSING":
        note = (
            "python-security-scan: `ruff` is not installed; Python security "
            "scanning is OFF. Install via `uv tool install ruff@latest` (or "
            "`pipx install ruff`) for OWASP/Bandit-aligned high-confidence "
            "anti-pattern detection on Python edits."
        )
        emit_note("PostToolUse", note)
        return
    if not findings:
        return

    lines = []
    for f in findings[:10]:
        code = f.get("code", "?")
        ln = (f.get("location") or {}).get("row", "?")
        msg = (f.get("message") or "").strip()
        label = RULE_LABELS.get(code, "")
        lines.append(f"  L{ln} — {code} {label}: {msg}")
    more = f"\n  …and {len(findings) - 10} more" if len(findings) > 10 else ""

    note = (
        f"python-security-scan caught {len(findings)} finding(s) in "
        f"{file_path}:\n" + "\n".join(lines) + more +
        "\nThese are OWASP/Bandit-aligned dangerous patterns (S-rules) and "
        "zero-FP correctness bugs (B-rules) enforced via the ruff curated "
        "subset. Inline `# noqa` is NOT honored — a genuine exception "
        "surfaces via the `surface-ticket` skill, not as a silenced marker. "
        "Resolve before declaring done."
    )
    emit_note("PostToolUse", note)


if __name__ == "__main__":
    run(main)
