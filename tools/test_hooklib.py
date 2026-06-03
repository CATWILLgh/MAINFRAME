#!/usr/bin/env python3
"""Unit tests for the shared `_hooklib` hook scaffolding.

Run: `python3 tools/test_hooklib.py` (exit 0 = pass). Stdlib only. The git-backed
tests build a throwaway repo in a temp dir, so they need `git` on PATH.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "plugin-dist", "hooks", "scripts"))
import _hooklib  # noqa: E402


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _repo():
    d = tempfile.mkdtemp()
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t")
    _git(d, "config", "user.name", "t")
    return d


def _write(d, name, text):
    with open(os.path.join(d, name), "w") as f:
        f.write(text)


def test_ext():
    assert _hooklib.ext("/a/b.PY") == ".py"
    assert _hooklib.ext("/a/Makefile") == ""
    assert _hooklib.ext("x.tar.gz") == ".gz"
    assert _hooklib.ext("/dir.with.dot/name") == ""


def test_stop_guard_cwd():
    assert _hooklib.stop_guard_cwd({"stop_hook_active": True}) is None
    assert _hooklib.stop_guard_cwd({"cwd": "/x"}) == "/x"
    assert _hooklib.stop_guard_cwd({}) == "."


def test_load_payload():
    old = sys.stdin
    try:
        sys.stdin = io.StringIO('{"a": 1}')
        assert _hooklib.load_payload() == {"a": 1}
        sys.stdin = io.StringIO("not json")
        assert _hooklib.load_payload() == {}
    finally:
        sys.stdin = old


def test_emit_note_and_block():
    buf = io.StringIO()
    with redirect_stdout(buf):
        _hooklib.emit_note("PostToolUse", "hi")
    out = json.loads(buf.getvalue())
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert out["hookSpecificOutput"]["additionalContext"] == "hi"
    buf = io.StringIO()
    with redirect_stdout(buf):
        _hooklib.emit_block("nope")
    out = json.loads(buf.getvalue())
    assert out == {"decision": "block", "reason": "nope"}


def test_added_lines_by_file():
    d = _repo()
    try:
        _write(d, "a.py", "x = 1\n")
        _write(d, "readme.md", "hello\n")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "base")
        _write(d, "a.py", "x = 1\ny = 2\n")        # added source line
        _write(d, "readme.md", "hello\nworld\n")   # md is not CODE_EXTENSIONS
        rows = _hooklib.added_lines_by_file(d)
        bodies = [body for _, body in rows]
        exts = {e for e, _ in rows}
        assert "y = 2" in bodies
        assert exts == {".py"}                      # markdown skipped
        # self-file skip: a change to a HUB_HOOK_FILES name is not reported
        _write(d, "_markers.py", "TODO\n")
        _git(d, "add", "_markers.py")
        rows2 = _hooklib.added_lines_by_file(d)
        assert all(b != "TODO" for _, b in rows2)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_added_lines_no_repo():
    d = tempfile.mkdtemp()  # fresh dir, not a git work tree
    try:
        assert _hooklib.added_lines_by_file(d) == []
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_git_head():
    d = _repo()
    try:
        _write(d, "a.py", "orig\n")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "base")
        assert _hooklib.read_git_head(os.path.join(d, "a.py")) == "orig\n"
        _write(d, "new.py", "x\n")                  # untracked
        assert _hooklib.read_git_head(os.path.join(d, "new.py")) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK _hooklib — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
