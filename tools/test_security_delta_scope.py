#!/usr/bin/env python3
"""Tests for _hooklib delta-scoping helpers: changed_line_ranges,
finding_is_delta, tickets_mentioning.

Design under test (harness feedback 2026-06-14 + 2026-06-23, reviewer-hardened):
security hooks classify findings as delta (changed this session) vs inherited;
EVERY ambiguity — no git, unparsed file, empty range entry — must fail toward
delta, the strict branch, never the weakened inherited one. Ticket matching
anchors on the repo-relative path, never the basename (basenames collide).
"""

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


def test_ranges_modified_line():
    root = _mk_repo()
    _rewrite_line(root, "legacy.py", 7, "line_7 = 'changed'\n")
    ranges, ok = hooklib.changed_line_ranges(root)
    assert ok is True
    assert ranges[os.path.join(root, "legacy.py")] == {7}


def test_ranges_single_insertion_omitted_count():
    root = _mk_repo()
    path = os.path.join(root, "legacy.py")
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    lines.insert(5, "inserted = True\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    ranges, ok = hooklib.changed_line_ranges(root)
    assert ok and ranges[path] == {6}


def test_ranges_deletion_only_marks_nothing():
    root = _mk_repo()
    path = os.path.join(root, "legacy.py")
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    del lines[9:12]
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    ranges, ok = hooklib.changed_line_ranges(root)
    assert ok and ranges[path] == set()


def test_ranges_untracked_file_is_all_new():
    root = _mk_repo()
    path = os.path.join(root, "fresh.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("a = 1\n")
    ranges, ok = hooklib.changed_line_ranges(root)
    assert ok and ranges[path] is None


def test_ranges_no_git_returns_not_ok():
    plain = os.path.realpath(tempfile.mkdtemp())
    ranges, ok = hooklib.changed_line_ranges(plain)
    assert ranges == {} and ok is False


def test_delta_when_git_unavailable():
    assert hooklib.finding_is_delta("/x/f.py", 5, 5, {}, False) is True


def test_delta_when_file_missing_from_ranges():
    assert hooklib.finding_is_delta("/x/f.py", 5, 5, {"/x/other.py": {1}}, True) is True


def test_delta_when_entry_empty_ambiguous():
    # Deletion-only / unparsed hunks leave an empty set: ambiguity -> strict.
    assert hooklib.finding_is_delta("/x/f.py", 5, 5, {"/x/f.py": set()}, True) is True


def test_delta_untracked_all_new():
    assert hooklib.finding_is_delta("/x/f.py", 999, 999, {"/x/f.py": None}, True) is True


def test_delta_overlap_spans_changed_line():
    ranges = {"/x/f.py": {10, 11}}
    assert hooklib.finding_is_delta("/x/f.py", 8, 10, ranges, True) is True
    assert hooklib.finding_is_delta("/x/f.py", 11, 15, ranges, True) is True


def test_inherited_when_fully_outside_ranges():
    ranges = {"/x/f.py": {10, 11}}
    assert hooklib.finding_is_delta("/x/f.py", 3, 5, ranges, True) is False
    assert hooklib.finding_is_delta("/x/f.py", 12, 15, ranges, True) is False


def _mk_tickets(root, name, body):
    tdir = os.path.join(root, "docs", "tickets")
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


def test_scan_inherited_unticketed_nudges_ticket():
    root = _mk_repo()
    path = _mk_legacy_py(root)
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4, "tail = 2\n")
    out = _run_hook("python-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert "inherited" in out and "surface-ticket" in out
    assert "Resolve before declaring done" not in out


def test_scan_inherited_ticketed_is_silent():
    root = _mk_repo()
    path = _mk_legacy_py(root)
    _mk_tickets(root, "abc12345-legacy-debt.md", "debt: `svc/legacy.py` B006\n")
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4, "tail = 2\n")
    out = _run_hook("python-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert out.strip() == ""


def test_scan_delta_finding_keeps_strong_note():
    root = _mk_repo()
    path = _mk_legacy_py(root)
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4,
                  "password = \"hunter2secret\"\n")
    out = _run_hook("python-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert "S105" in out and "Resolve before declaring done" in out
    assert "B006" not in out.split("inherited")[0]


def test_gate_inherited_unticketed_blocks_with_ticket_instruction():
    root = _mk_repo()
    _mk_legacy_py(root)
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4, "tail = 2\n")
    out = _run_hook("python-security-stop-gate.py", {"cwd": root})
    assert '"block"' in out and "inherited" in out and "B006" in out


def test_gate_inherited_ticketed_passes():
    root = _mk_repo()
    _mk_legacy_py(root)
    _mk_tickets(root, "abc12345-legacy-debt.md", "debt: `svc/legacy.py` B006\n")
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4, "tail = 2\n")
    out = _run_hook("python-security-stop-gate.py", {"cwd": root})
    assert out.strip() == ""


def test_gate_delta_finding_blocks_despite_ticket():
    root = _mk_repo()
    _mk_legacy_py(root)
    _mk_tickets(root, "abc12345-legacy-debt.md", "debt: `svc/legacy.py` all rules\n")
    _rewrite_line(root, os.path.join("svc", "legacy.py"), 4,
                  "password = \"hunter2secret\"\n")
    out = _run_hook("python-security-stop-gate.py", {"cwd": root})
    assert '"block"' in out and "S105" in out


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


def test_node_scan_inherited_unticketed_nudges_ticket():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    out = _run_hook("nodejs-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert "inherited" in out and "surface-ticket" in out
    assert "changed this session" not in out


def test_node_scan_inherited_ticketed_is_silent():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _mk_tickets(root, "abc12345-js-debt.md", "debt: `web/legacy.js` no-eval\n")
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    out = _run_hook("nodejs-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert out.strip() == ""


def test_node_scan_delta_finding_keeps_strong_note():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "eval(\"tail\");\n")
    out = _run_hook("nodejs-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert "changed this session" in out and "no-eval" in out


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
    out = _run_hook("nodejs-security-scan.py",
                    {"cwd": root, "tool_input": {"file_path": path}})
    assert out.strip() == ""


def _load_node_gate():
    gate_spec = importlib.util.spec_from_file_location(
        "node_gate", os.path.join(_SCRIPTS, "nodejs-security-stop-gate.py"))
    gate = importlib.util.module_from_spec(gate_spec)
    gate_spec.loader.exec_module(gate)
    return gate


def _gate_out(gate, root, findings):
    # Semgrep runs are network/registry-bound; inject findings and let the
    # real classifier + ticket check run against the fixture repo.
    import contextlib
    import io
    gate.load_payload = lambda: {"cwd": root}
    gate.changed_files = lambda cwd, exts: sorted({f["path"] for f in findings})
    gate._run_semgrep = lambda files: findings
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        gate.main()
    return buf.getvalue()


def test_node_gate_inherited_ticketed_passes():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _mk_tickets(root, "abc12345-js-debt.md", "debt: `web/legacy.js` eval\n")
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    finding = {"path": path, "check_id": "js.eval", "start": {"line": 2},
               "end": {"line": 2}, "extra": {"message": "eval"}}
    assert _gate_out(_load_node_gate(), root, [finding]).strip() == ""


def test_node_gate_inherited_unticketed_blocks():
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    finding = {"path": path, "check_id": "js.eval", "start": {"line": 2},
               "end": {"line": 2}, "extra": {"message": "eval"}}
    out = _gate_out(_load_node_gate(), root, [finding])
    assert '"block"' in out and "inherited" in out


def test_node_gate_multiline_overlap_is_delta():
    # Reviewer mitigation: a finding spanning into a changed line is delta even
    # when its start line is untouched (semgrep anchors multiline findings).
    root = _mk_repo()
    path = _mk_legacy_js(root)
    _mk_tickets(root, "abc12345-js-debt.md", "debt: `web/legacy.js` eval\n")
    _rewrite_line(root, os.path.join("web", "legacy.js"), 3, "const tail = 2;\n")
    finding = {"path": path, "check_id": "js.eval", "start": {"line": 2},
               "end": {"line": 3}, "extra": {"message": "eval"}}
    out = _gate_out(_load_node_gate(), root, [finding])
    assert '"block"' in out and "changed this session" in out


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
