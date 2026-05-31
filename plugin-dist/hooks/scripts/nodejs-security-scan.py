#!/usr/bin/env python3
"""PostToolUse hook: scan freshly-written/edited JS/TS files for high-confidence
dangerous patterns via oxlint's curated rule subsets.

Reads the PostToolUse hook payload from stdin (JSON), filters to .js/.ts/.mjs/
.cjs/.jsx/.tsx edits, runs `oxlint -A all -D <subset> --format=json` on the
file (with extension-aware rule set + plugin flags), and emits a non-blocking
`additionalContext` note with the findings.

Design (honestly framed — partial coverage, NOT a full Node-security gate):
- BASE_RULES (all JS/TS): `eslint/no-eval`, `eslint/no-new-func` — classic RCE
  vectors via dynamic code execution. Source: oxc.rs/docs/guide/usage/linter.
  Verified per ADR 0058 iteration-2 on synthetic bad-JS.
- JSX_REACT_RULES (.tsx/.jsx only): `react/no-danger` (dangerouslySetInnerHTML),
  `react/jsx-no-script-url` (href="javascript:..."), `react/jsx-no-target-blank`
  (target="_blank" without rel=noreferrer). Verified per ADR 0061 probe on
  synthetic violations.tsx + 0 FP on shadcn-style clean component.
- JSX_A11Y_RULES (.tsx/.jsx only): `jsx-a11y/alt-text` (img without alt),
  `jsx-a11y/anchor-is-valid` (a without href / bad href),
  `jsx-a11y/aria-role` (invalid ARIA role). Verified per ADR 0061 probe on
  synthetic violations.tsx + 0 FP on shadcn `<Avatar>`/`<Label>`/`<Field>`.
- `react-perf-plugin` deliberately EXCLUDED — empirically a FP firehose
  (fires on every `onClick={handler}` from `useState` + every `style={{}}`).
  Skip per ADR 0061 + ADR 0056 curation lesson.
- Out of scope for this per-edit hook: weak crypto, TLS verification disabled,
  YAML unsafe load, hardcoded credentials, full Semgrep p/security-audit
  ruleset. Partially covered at Stop by `nodejs-security-stop-gate.py`.
- Non-blocking: PostToolUse cannot block; only emits additionalContext.
- Fail-safe: ANY error → exit 0 with no output. Missing oxlint → install hint.
- Invocation strategy: prefer local binary (`oxlint` in PATH, ~100-300ms);
  fall back to `npx --yes oxlint@latest` (~700ms warm, slower cold).
- Stdlib only on Python side; shells out to `oxlint` or `npx`.
"""

import json
import os
import shutil
import subprocess
import sys

BASE_RULES = ["no-eval", "no-new-func"]
JSX_REACT_RULES = ["react/no-danger", "react/jsx-no-script-url", "react/jsx-no-target-blank"]
JSX_A11Y_RULES = ["jsx-a11y/alt-text", "jsx-a11y/anchor-is-valid", "jsx-a11y/aria-role"]
JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
JSX_EXTS = (".tsx", ".jsx")


def _ext(path):
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    return path[dot:].lower() if dot > slash else ""


def _oxlint_cmd():
    """Return the command-prefix for oxlint, or None if unavailable."""
    binary = shutil.which("oxlint")
    if binary:
        return [binary]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "oxlint@latest"]
    return None


def _run_oxlint(file_path):
    cmd = _oxlint_cmd()
    if cmd is None:
        return "OXLINT_MISSING"
    ext = _ext(file_path)
    args = cmd + ["-A", "all", "--format=json"]
    rules = list(BASE_RULES)
    if ext in JSX_EXTS:
        args.extend(["--react-plugin", "--jsx-a11y-plugin"])
        rules.extend(JSX_REACT_RULES)
        rules.extend(JSX_A11Y_RULES)
    for rule in rules:
        args.extend(["-D", rule])
    args.append(file_path)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    if proc.returncode not in (0, 1):
        return None
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return None
    diags = data.get("diagnostics", []) if isinstance(data, dict) else []
    return diags


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or _ext(file_path) not in JS_EXTS:
        return
    if not os.path.exists(file_path):
        return

    diags = _run_oxlint(file_path)
    if diags is None:
        return
    if diags == "OXLINT_MISSING":
        note = (
            "nodejs-security-scan: neither `oxlint` nor `npx` is installed; "
            "Node code security scanning is OFF. Install via `npm install -g "
            "oxlint` (or any `npx`-providing Node setup) for eval / Function-"
            "constructor detection on JS/TS edits."
        )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse", "additionalContext": note}}))
        return
    if not diags:
        return

    lines = []
    for d in diags[:10]:
        code = d.get("code", "?").replace("eslint(", "").rstrip(")")
        labels = d.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        ln = span.get("line", "?")
        msg = (d.get("message") or "").strip()[:120]
        lines.append(f"  L{ln} — {code}: {msg}")
    more = f"\n  …and {len(diags) - 10} more" if len(diags) > 10 else ""

    ext = _ext(file_path)
    if ext in JSX_EXTS:
        coverage = (
            "Covered: eval/Function-constructor (no-eval, no-new-func) + React XSS "
            "vectors (no-danger, jsx-no-script-url, jsx-no-target-blank) + core a11y "
            "(alt-text, anchor-is-valid, aria-role)."
        )
    else:
        coverage = (
            "Covered: `eval()` (no-eval) + `new Function(string)` / `Function(string)` "
            "(no-new-func)."
        )
    note = (
        f"nodejs-security-scan caught {len(diags)} finding(s) in {file_path}:\n"
        + "\n".join(lines) + more +
        f"\n{coverage} NOT covered by this per-edit hook: weak crypto (md5/sha1), "
        "TLS `rejectUnauthorized: false`, YAML unsafe load, hardcoded credentials, "
        "setTimeout/setInterval with string (implied eval), localStorage token "
        "storage. Broader coverage at Stop boundary via Semgrep `p/security-audit` "
        "+ hub localStorage rule. Inline `// oxlint-disable` is NOT honored — "
        "genuine exceptions surface via the `surface-ticket` skill."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": note}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
