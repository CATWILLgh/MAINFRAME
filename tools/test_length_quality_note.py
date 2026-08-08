#!/usr/bin/env python3
"""Tests for length-quality-note.py (Stop hook, advisory-only, no delta split).

Covers: file-length and function-length violations fire a note; a ticket
naming the file suppresses BOTH checks for that file (uniform suppression,
per decision-reviewer's adopted counter-model); a SyntaxError in a changed
Python file skips only the function check, the file-length check still runs;
.sql is excluded from the file-length check (FILE_LENGTH_EXTENSIONS carve-out);
the stop_hook_active loop guard is honored; a short file stays silent.
"""

import json
import os
import subprocess
import sys
import tempfile

_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "adapters/claude-code/plugin", "hooks", "scripts")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _mk_repo():
    root = os.path.realpath(tempfile.mkdtemp())
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("base\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _add_new_file(root, rel, text):
    # Deliberately UNTRACKED (no `git add`) -- this is how the Write tool
    # actually leaves a freshly created file; `git diff HEAD` never sees it.
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _mk_ticket(root, name, body):
    tdir = os.path.join(root, "docs", "tickets")
    os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, name), "w", encoding="utf-8") as fh:
        fh.write(body)


def _long_lines(n):
    return "".join(f"x_{i} = {i}\n" for i in range(n))


def _run_hook(payload_dict):
    proc = subprocess.run(
        [sys.executable, os.path.join(_SCRIPTS, "length-quality-note.py")],
        input=json.dumps(payload_dict), capture_output=True, text=True, timeout=30)
    return proc.stdout


def test_no_changed_files_is_silent():
    root = _mk_repo()
    assert _run_hook({"cwd": root}).strip() == ""


def test_short_file_is_silent():
    root = _mk_repo()
    _add_new_file(root, "small.py", "x = 1\n")
    assert _run_hook({"cwd": root}).strip() == ""


def test_new_long_file_no_ticket_fires_note():
    root = _mk_repo()
    _add_new_file(root, "big.go", _long_lines(405))
    out = _run_hook({"cwd": root})
    assert "big.go" in out and "405 lines" in out


def test_new_long_file_staged_also_fires_note():
    # Defense: a file already `git add`-ed before Stop fires must still be
    # caught via `changed_files`, not just via the untracked path.
    root = _mk_repo()
    _add_new_file(root, "staged.go", _long_lines(405))
    _git(root, "add", "staged.go")
    out = _run_hook({"cwd": root})
    assert "staged.go" in out and "405 lines" in out


def test_new_long_file_ticketed_is_silent():
    root = _mk_repo()
    _add_new_file(root, "big.go", _long_lines(405))
    _mk_ticket(root, "abc12345-big-debt.md", "debt: `big.go` is oversized\n")
    assert _run_hook({"cwd": root}).strip() == ""


def test_python_long_function_no_ticket_fires_note():
    root = _mk_repo()
    src = "def big():\n" + "    x = 1\n" * 65
    _add_new_file(root, "svc/big_func.py", src)
    out = _run_hook({"cwd": root})
    assert "big_func.py" in out and "`big`" in out


def test_python_long_function_ticketed_is_silent():
    root = _mk_repo()
    src = "def big():\n" + "    x = 1\n" * 65
    _add_new_file(root, "svc/big_func.py", src)
    _mk_ticket(root, "abc12345-func-debt.md", "debt: `svc/big_func.py` too long\n")
    assert _run_hook({"cwd": root}).strip() == ""


def test_malformed_python_skips_function_check_file_check_still_runs():
    root = _mk_repo()
    # Syntax error PLUS over the file-length threshold in the same file.
    src = "def broken(:\n" + _long_lines(405)
    _add_new_file(root, "broken.py", src)
    out = _run_hook({"cwd": root})
    assert "broken.py" in out and "file(s) over" in out
    assert "function(s) over" not in out


def test_sql_file_excluded_from_file_length_check():
    root = _mk_repo()
    _add_new_file(root, "schema.sql", _long_lines(450))
    assert _run_hook({"cwd": root}).strip() == ""


def test_stop_hook_active_guard_is_silent():
    root = _mk_repo()
    _add_new_file(root, "big.go", _long_lines(405))
    assert _run_hook({"cwd": root, "stop_hook_active": True}).strip() == ""


def _run_all():
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
