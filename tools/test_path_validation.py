#!/usr/bin/env python3
"""Unit tests for the path-validation PreToolUse gate.

Run: `python3 tools/test_path_validation.py` (exit 0 = pass). Stdlib only,
Tier 1. Drives `main()` with fake stdin and captured stdout; covers the
`project_dir` payload field (used by the OpenCode adapter plugin, where the
`CLAUDE_PROJECT_DIR` env contract does not exist) and its env fallback.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile

_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "dist", "claude-code", "plugin", "hooks", "scripts")


def _load():
    path = os.path.join(_SCRIPTS, "path-validation.py")
    spec = importlib.util.spec_from_file_location("path_validation", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pv = _load()


def _run(payload, env_project=None):
    """Run main() with a fake stdin; return the decision JSON or None."""
    old_stdin, old_stdout = sys.stdin, sys.stdout
    old_env = os.environ.get("CLAUDE_PROJECT_DIR")
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    if env_project is None:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
    else:
        os.environ["CLAUDE_PROJECT_DIR"] = env_project
    try:
        try:
            pv.main()
        except SystemExit:
            pass
        out = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
        if old_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = old_env
    if not out.strip():
        return None
    return json.loads(out)["hookSpecificOutput"]


def _payload(command, cwd, project_dir=None):
    p = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    if project_dir is not None:
        p["project_dir"] = project_dir
    return p


def test_payload_project_dir_allows_inside_target():
    proj = tempfile.mkdtemp()
    os.makedirs(os.path.join(proj, "sub"))
    got = _run(_payload(f"rm -rf {proj}/sub", proj, project_dir=proj))
    assert got is not None and got["permissionDecision"] == "allow", got


def test_payload_project_dir_asks_for_outside_target():
    proj = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    got = _run(_payload(f"rm -rf {outside}", proj, project_dir=proj))
    assert got is not None and got["permissionDecision"] == "ask", got


def test_env_fallback_still_works():
    proj = tempfile.mkdtemp()
    os.makedirs(os.path.join(proj, "sub"))
    got = _run(_payload(f"rm -rf {proj}/sub", proj), env_project=proj)
    assert got is not None and got["permissionDecision"] == "allow", got


def test_payload_project_dir_wins_over_env():
    proj = tempfile.mkdtemp()
    other = tempfile.mkdtemp()
    os.makedirs(os.path.join(proj, "sub"))
    got = _run(_payload(f"rm -rf {proj}/sub", proj, project_dir=proj),
               env_project=other)
    assert got is not None and got["permissionDecision"] == "allow", got


def test_non_rm_command_defers_silently():
    got = _run(_payload("git status", tempfile.mkdtemp(),
                        project_dir=tempfile.mkdtemp()))
    assert got is None, got


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
