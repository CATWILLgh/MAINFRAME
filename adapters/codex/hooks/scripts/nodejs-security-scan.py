#!/usr/bin/env python3
"""PostToolUse hook: scan freshly-written/edited JS/TS files for high-confidence
dangerous patterns via oxlint's curated rule subsets.

Reads the PostToolUse hook payload from stdin, filters to JS/TS edits, runs the
curated Oxlint subset, and emits a short note only for findings on lines written
by that exact tool call. Pre-existing findings elsewhere stay silent.

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
- Out of scope for this narrow per-edit hook: broader project security and
  dependency audits. Those belong to explicit project work.
- Non-blocking: PostToolUse cannot block; only emits additionalContext.
- Missing or broken Oxlint is handled by the common once-per-session hook
  failure reporter; the hook never downloads a tool during an edit.
- Stdlib only on Python side; shells out to the installed `oxlint` binary.
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _hooklib import emit_note, ext, load_payload, log_hook_signal, run
except Exception:
    sys.exit(0)

BASE_RULES = ["no-eval", "no-new-func"]
JSX_REACT_RULES = ["react/no-danger", "react/jsx-no-script-url", "react/jsx-no-target-blank"]
JSX_A11Y_RULES = ["jsx-a11y/alt-text", "jsx-a11y/anchor-is-valid", "jsx-a11y/aria-role"]
JS_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
JSX_EXTS = (".tsx", ".jsx")


def _oxlint_cmd():
    """Return the installed Oxlint command without network fallbacks."""
    binary = shutil.which("oxlint")
    if binary:
        return [binary]
    raise RuntimeError(
        "Node safety checks are unavailable because `oxlint` is missing. "
        "Install it with `npm install -g oxlint`."
    )


def _run_oxlint(file_path):
    cmd = _oxlint_cmd()
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
    except Exception as exc:
        raise RuntimeError("Node safety checks failed to run Oxlint") from exc
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        suffix = f": {detail[0][:240]}" if detail else ""
        raise RuntimeError(f"Node safety checks failed to run{suffix}")
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Node safety checks returned invalid Oxlint JSON") from exc
    diags = data.get("diagnostics", []) if isinstance(data, dict) else []
    return diags


def _matching_spans(text, value):
    if not value:
        return []
    spans = []
    start = 0
    while True:
        index = text.find(value, start)
        if index < 0:
            return spans
        first = text.count("\n", 0, index) + 1
        last = first + value.count("\n")
        spans.append((first, last))
        start = index + max(1, len(value))


def _tool_spans(tool_name, tool_input, text):
    if tool_name == "Write":
        return [(1, max(1, text.count("\n") + 1))]
    if tool_name == "Edit":
        spans = _matching_spans(text, tool_input.get("new_string", "") or "")
        if tool_input.get("replace_all") or len(spans) <= 1:
            return spans
        return []
    if tool_name == "MultiEdit":
        spans = []
        for edit in tool_input.get("edits", []) or []:
            matches = _matching_spans(text, edit.get("new_string", "") or "")
            if edit.get("replace_all") or len(matches) <= 1:
                spans.extend(matches)
        return spans
    return []


def main():
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "MultiEdit", "Write"):
        return
    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "")
    if not file_path or ext(file_path) not in JS_EXTS:
        return
    if not os.path.exists(file_path):
        return
    with open(file_path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    changed_spans = _tool_spans(tool_name, tool_input, text)
    if not changed_spans:
        return

    diags = _run_oxlint(file_path)
    # Parser diagnostics arrive with code=None regardless of -D rule selection
    # (a mid-edit-cluster file is transiently broken JSX); syntax belongs to
    # tsc/build, not this scan — only rule-coded findings pass.
    diags = [d for d in diags if d.get("code")]
    if not diags:
        return

    delta = []
    for d in diags:
        labels = d.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        ln = span.get("line") or 0
        if any(start <= ln <= end for start, end in changed_spans):
            delta.append(d)
    if not delta:
        return
    diags = delta

    lines = []
    for d in diags[:6]:
        code = d.get("code", "?").replace("eslint(", "").rstrip(")")
        labels = d.get("labels") or []
        span = labels[0].get("span", {}) if labels else {}
        ln = span.get("line", "?")
        msg = (d.get("message") or "").strip()[:120]
        lines.append(f"  L{ln} — {code}: {msg}")
    more = f"\n  …and {len(diags) - 6} more" if len(diags) > 6 else ""
    cwd = payload.get("cwd") or os.getcwd()
    display_path = os.path.relpath(file_path, cwd)
    note = (
        f"Node safety check found {len(diags)} issue(s) on lines written by "
        f"this tool call in {display_path}:\n"
        + "\n".join(lines) + more +
        "\nResolve the underlying code before completion; suppressing the "
        "diagnostic does not resolve it."
    )
    emit_note("PostToolUse", note)
    log_hook_signal(
        __file__, "node-safety", "noted", len(diags), payload, context=note
    )


if __name__ == "__main__":
    run(main)
