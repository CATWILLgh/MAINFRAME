#!/usr/bin/env python3
"""Regression tests for ticket matching and the delta-only Node scanner."""

import importlib.util
import os
import subprocess
import tempfile

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "adapters/claude-code/plugin", "hooks", "scripts", "_hooklib.py")
spec = importlib.util.spec_from_file_location("hooklib_ds", _SCRIPT)
hooklib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooklib)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _mk_repo():
    root = os.path.realpath(tempfile.mkdtemp())
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    with open(os.path.join(root, "legacy.py"), "w", encoding="utf-8") as fh:
        fh.write("".join(f"line_{n} = {n}\n" for n in range(1, 31)))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _rewrite_line(root, name, lineno, text):
    path = os.path.join(root, name)
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    lines[lineno - 1] = text
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def _mk_tickets(root, name, body):
    tdir = os.path.join(root, "docs", "tickets", "open", "observations")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, name), "w", encoding="utf-8") as fh:
        fh.write(body)


def test_tickets_match_on_relative_path():
    root = _mk_repo()
    target = os.path.join(root, "services", "auth.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    _mk_tickets(root, "abc12345-auth-debt.md",
                "## What was observed\nfindings in `services/auth.py` L9\n")
    assert hooklib.tickets_mentioning(root, target) == ["abc12345-auth-debt.md"]


def test_tickets_match_recursively_across_open_states():
    root = _mk_repo()
    target = os.path.join(root, "services", "auth.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    tdir = os.path.join(root, "docs", "tickets", "open", "ready")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, "2e7c-auth-debt.md"), "w", encoding="utf-8") as fh:
        fh.write("findings in `services/auth.py`\n")
    assert hooklib.tickets_mentioning(root, target) == ["2e7c-auth-debt.md"]


def test_tickets_ignore_archive():
    root = _mk_repo()
    target = os.path.join(root, "services", "auth.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    tdir = os.path.join(root, "docs", "tickets", "archive", "resolved")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, "2e7c-old-auth-debt.md"), "w", encoding="utf-8") as fh:
        fh.write("findings in `services/auth.py`\n")
    assert hooklib.tickets_mentioning(root, target) == []


def test_tickets_basename_only_does_not_match():
    # `auth.py` alone must not cover services/auth.py — basenames collide
    # (auth.py is a substring of oauth.py; utils.py recurs across a repo).
    root = _mk_repo()
    target = os.path.join(root, "services", "auth.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    _mk_tickets(root, "abc12345-auth-debt.md", "debt in auth.py fixtures\n")
    assert hooklib.tickets_mentioning(root, target) == []


def test_tickets_no_dir_returns_empty():
    root = _mk_repo()
    assert hooklib.tickets_mentioning(root, os.path.join(root, "legacy.py")) == []


def test_tickets_readme_ignored():
    root = _mk_repo()
    _mk_tickets(root, "README.md", "mentions legacy.py path legacy.py\n")
    assert hooklib.tickets_mentioning(root, os.path.join(root, "legacy.py")) == []


_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "adapters/claude-code/plugin", "hooks", "scripts")


def _run_hook(script, payload_dict):
    import json
    proc = subprocess.run(
        [os.sys.executable, os.path.join(_SCRIPTS, script)],
        input=json.dumps(payload_dict), capture_output=True, text=True, timeout=60)
    return proc.stdout


def _mk_legacy_py(root):
    # Line 2 carries a pre-existing B006 (mutable default) committed in HEAD.
    path = os.path.join(root, "svc", "legacy.py")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("import os\n"
                 "def f(x=[]):\n"
                 "    return x\n"
                 "tail = 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "legacy")
    return path


def _mk_legacy_js(root):
    # Line 2 carries a pre-existing eval() committed in HEAD.
    path = os.path.join(root, "web", "legacy.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("const a = 1;\n"
                 "eval(\"a\");\n"
                 "const tail = 1;\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "legacy js")
    return path


def test_node_scan_preexisting_finding_stays_silent():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    out = _run_hook("nodejs-security-scan.py", {
        "cwd": root, "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "const tail = 1;",
                       "new_string": "const tail = 2;"},
    })
    assert out.strip() == ""


def test_node_scan_ambiguous_repeated_replacement_stays_silent():
    root = _mk_repo()
    path = os.path.join(root, "web", "repeated.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('eval("same");\neval("same");\n')
    out = _run_hook("nodejs-security-scan.py", {
        "cwd": root, "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "safe();",
                       "new_string": 'eval("same");'},
    })
    assert out.strip() == ""


def test_node_scan_delta_finding_keeps_strong_note():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "eval(\"tail\");\n")
    out = _run_hook("nodejs-security-scan.py", {
        "cwd": root, "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": "const tail = 1;",
                       "new_string": "eval(\"tail\");"},
    })
    assert "this tool call" in out and "no-eval" in out


def test_node_scan_parse_errors_are_dropped():
    # oxlint emits parser diagnostics (code: None) regardless of -D rule
    # selection; a mid-edit-cluster file is transiently broken JSX, and those
    # phantoms must not surface — syntax belongs to tsc/build, not this scan.
    root = _mk_repo()
    path = os.path.join(root, "web", "broken.tsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("export function B() {\n"
                 "  return (\n"
                 "    <div>\n"
                 "      {items.map((x) => (\n"
                 "        <span key={x}>{x}</span>\n"
                 "      )}\n"
                 "    </div>\n"
                 "  );\n"
                 "}\n")
    out = _run_hook("nodejs-security-scan.py", {
        "cwd": root, "tool_name": "Write", "tool_input": {"file_path": path},
    })
    assert out.strip() == ""


def _run_all():
    import sys
    failures = 0
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
