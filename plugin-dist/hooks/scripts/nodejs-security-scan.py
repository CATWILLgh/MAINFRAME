#!/usr/bin/env python3
"""PostToolUse hook: scan freshly-written/edited JS/TS files for high-confidence
dangerous patterns via oxlint's curated rule subsets.

Reads the PostToolUse hook payload from stdin (JSON), filters to .js/.ts/.mjs/
.cjs/.jsx/.tsx edits, runs `oxlint -A all -D <subset> --format=json` on the
file (with extension-aware rule set + plugin flags), and emits a non-blocking
`additionalContext` note. Findings are split by changed-line overlap: delta
findings get the resolve-now note; inherited (untouched-line) findings only
nudge toward a ticket, and only while no ticket names the file. Ambiguous
classification counts as delta.

Design (honestly framed — partial coverage, NOT a full Node-security gate):
- BASE_RULES (all JS/TS): `eslint/no-eval`, `eslint/no-new-func` — classic RCE
  vectors via dynamic code execution. Source: oxc.rs/docs/guide/usage/linter.
  Verified on synthetic bad-JS.
- JSX_REACT_RULES (.tsx/.jsx only): `react/no-danger` (dangerouslySetInnerHTML),
  `react/jsx-no-script-url` (href="javascript:..."), `react/jsx-no-target-blank`
  (target="_blank" without rel=noreferrer). Verified by probe on
  synthetic violations.tsx + 0 FP on shadcn-style clean component.
- JSX_A11Y_RULES (.tsx/.jsx only): `jsx-a11y/alt-text` (img without alt),
  `jsx-a11y/anchor-is-valid` (a without href / bad href),
  `jsx-a11y/aria-role` (invalid ARIA role). Verified by probe on
  synthetic violations.tsx + 0 FP on shadcn `<Avatar>`/`<Label>`/`<Field>`.
- `react-perf-plugin` deliberately EXCLUDED — empirically a FP firehose
  (fires on every `onClick={handler}` from `useState` + every `style={{}}`).
  Skip per curation lesson on per-edit FP cost.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import (changed_line_ranges, emit_note, ext, finding_is_delta,
                          load_payload, run, tickets_mentioning)
except Exception:
    sys.exit(0)

BASE_RULES = ["no-eval", "no-new-func"]
JSX_REACT_RULES = ["react/no-danger", "react/jsx-no-script-url", "react/jsx-no-target-blank"]
JSX_A11Y_RULES = ["jsx-a11y/alt-text", "jsx-a11y/anchor-is-valid", "jsx-a11y/aria-role"]
JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
JSX_EXTS = (".tsx", ".jsx")


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
    file_ext = ext(file_path)
    args = cmd + ["-A", "all", "--format=json"]
    rules = list(BASE_RULES)
    if file_ext in JSX_EXTS:
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


_MISSING_NOTE = (
    "nodejs-security-scan: neither `oxlint` nor `npx` is installed; "
    "Node code security scanning is OFF. Install via `npm install -g "
    "oxlint` (or any `npx`-providing Node setup) for eval / Function-"
    "constructor detection on JS/TS edits."
)


def _split_delta(diags, file_path, cwd):
    """Split diagnostics into (delta, inherited) by changed-line overlap."""
    ranges, git_ok = changed_line_ranges(cwd)
    delta, inherited = [], []
    for d in diags:
        labels = d.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        ln = span.get("line") or 0
        target = delta if finding_is_delta(file_path, ln, ln, ranges, git_ok) \
            else inherited
        target.append(d)
    return delta, inherited


def _inherited_note(file_path, inherited):
    codes = sorted({(d.get("code", "?")).replace("eslint(", "").rstrip(")")
                    for d in inherited})
    return (f"{len(inherited)} inherited finding(s) on untouched lines in "
            f"{file_path} ({', '.join(codes)}) — pre-existing debt, not "
            "this edit's job to fix, but no ticket covers this file: "
            "create or update one via the `surface-ticket` skill, "
            "mentioning the file's repo-relative path and the codes.")


def _delta_note(file_path, diags):
    lines = []
    for d in diags[:10]:
        code = d.get("code", "?").replace("eslint(", "").rstrip(")")
        labels = d.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        ln = span.get("line", "?")
        msg = (d.get("message") or "").strip()[:120]
        lines.append(f"  L{ln} — {code}: {msg}")
    more = f"\n  …and {len(diags) - 10} more" if len(diags) > 10 else ""

    if ext(file_path) in JSX_EXTS:
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
    return (
        f"nodejs-security-scan caught {len(diags)} finding(s) on lines changed "
        f"this session in {file_path}:\n"
        + "\n".join(lines) + more +
        f"\n{coverage} NOT covered by this per-edit hook: weak crypto (md5/sha1), "
        "TLS `rejectUnauthorized: false`, YAML unsafe load, hardcoded credentials, "
        "setTimeout/setInterval with string (implied eval), localStorage token "
        "storage. Broader coverage at Stop boundary via Semgrep `p/security-audit` "
        "+ hub localStorage rule. Inline `// oxlint-disable` is NOT honored — "
        "genuine exceptions surface via the `surface-ticket` skill."
    )


def main():
    payload = load_payload()
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or ext(file_path) not in JS_EXTS:
        return
    if not os.path.exists(file_path):
        return

    diags = _run_oxlint(file_path)
    if diags is None:
        return
    if diags == "OXLINT_MISSING":
        emit_note("PostToolUse", _MISSING_NOTE)
        return
    # Parser diagnostics arrive with code=None regardless of -D rule selection
    # (a mid-edit-cluster file is transiently broken JSX); syntax belongs to
    # tsc/build, not this scan — only rule-coded findings pass.
    diags = [d for d in diags if d.get("code")]
    if not diags:
        return

    # Delta vs inherited mirrors python-security-scan: only findings on lines
    # changed this session demand fixing now; untouched-line debt routes to
    # ticket discipline. Ambiguity always classifies as delta (strict).
    cwd = payload.get("cwd") or os.getcwd()
    delta, inherited = _split_delta(diags, file_path, cwd)

    if inherited and not tickets_mentioning(cwd, file_path):
        emit_note("PostToolUse", _inherited_note(file_path, inherited))
    if not delta:
        return
    emit_note("PostToolUse", _delta_note(file_path, delta))


if __name__ == "__main__":
    run(main)
