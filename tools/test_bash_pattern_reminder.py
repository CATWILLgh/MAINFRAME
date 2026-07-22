#!/usr/bin/env python3
"""Tests for bash-pattern-reminder.py — the known-Bash-traps nudge.

Focus: the rg replace-cluster rule (feedback 2026-06-29): in ripgrep `-r`
takes a REPLACEMENT value, so grep-muscle-memory clusters silently rewrite
matched text in the output (`-rln` = `--replace=ln`) and read as corruption.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile

os.environ["MAINFRAME_TELEMETRY_DB"] = os.path.join(
    tempfile.mkdtemp(prefix="bpr-telemetry-"), "telemetry.db")
_DIAGNOSTICS_CONFIG = os.path.join(
    os.path.dirname(os.environ["MAINFRAME_TELEMETRY_DB"]), "diagnostics.json")
with open(_DIAGNOSTICS_CONFIG, "w", encoding="utf-8") as _config:
    json.dump({"schema_version": 1, "events": True}, _config)
os.environ["MAINFRAME_DIAGNOSTICS_CONFIG"] = _DIAGNOSTICS_CONFIG

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "dist", "claude-code", "plugin", "hooks", "scripts", "bash-pattern-reminder.py")
spec = importlib.util.spec_from_file_location("bash_pattern_reminder", SCRIPT)
bpr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bpr)


def _drive(command, tool="Bash"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool,
               "tool_input": {"command": command}, "session_id": "t"}
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout)
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = out
        bpr.main()
    finally:
        (sys.stdin, sys.stdout) = saved
    return out.getvalue()


def test_rg_cluster_r_first_fires():
    out = _drive('rg -rln "dto/move-nm|dto/media-save" src/modules')
    assert "ripgrep" in out and "REPLACEMENT" in out


def test_rg_cluster_r_mid_fires():
    assert "ripgrep" in _drive('rg -irn "capKopecks" src')


def test_rg_cluster_trailing_r_fires():
    # `-nr` ends in r: the NEXT token becomes the replacement value.
    assert "ripgrep" in _drive('rg -nr pattern src/')


def test_rg_plain_flags_silent():
    assert _drive('rg -n "capKopecks|spentKopecks" src').strip() == ""


def test_rg_deliberate_replace_forms_silent():
    assert _drive("rg -r ln 'pat' src").strip() == ""
    assert _drive("rg --replace=ln 'pat' src").strip() == ""


def test_non_bash_tool_silent():
    assert _drive('rg -rln x', tool="Read").strip() == ""


def test_existing_rm_rf_rule_still_fires():
    assert "rm -r" in _drive("rm -rf /tmp/probe-x")


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
