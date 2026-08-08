#!/usr/bin/env python3
"""Tier-1 tests for task-workflow-engagement.py (re-activate the process skill).

Hyphenated hook loaded by path via importlib; the per-session state dir is
redirected to a throwaway tempdir so tests do not touch real state. main() is
driven with controlled stdin payloads and captured stdout.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin", "hooks", "scripts", "task-workflow-engagement.py")


def _load():
    spec = importlib.util.spec_from_file_location("tw_engagement", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load()
gate._STATE_DIR = tempfile.mkdtemp(prefix="tw-engage-test-")


def _drive(payload):
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout)
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = out
        gate.main()
    finally:
        (sys.stdin, sys.stdout) = saved
    return out.getvalue()


def _state(sid):
    return gate._read_state(gate._state_path(sid))


def _ss(sid):
    return {"hook_event_name": "SessionStart", "session_id": sid, "source": "compact"}


def _skill(sid, name):
    return {"hook_event_name": "PreToolUse", "session_id": sid,
            "tool_name": "Skill", "tool_input": {"skill": name}}


def _edit(sid, **kw):
    p = {"hook_event_name": "PreToolUse", "session_id": sid,
         "tool_name": "Edit", "tool_input": {"file_path": "x.py"}}
    p.update(kw)
    return p


def test_sessionstart_resets_to_fresh():
    _drive(_ss("s1"))
    assert _state("s1") == "fresh"


def test_skill_marks_active():
    _drive(_ss("s2"))
    _drive(_skill("s2", "task-workflow"))
    assert _state("s2") == "active"


def test_namespaced_skill_marks_active():
    _drive(_skill("s3", "mainframe:task-workflow"))
    assert _state("s3") == "active"


def test_other_skill_does_not_activate():
    _drive(_ss("s3b"))
    _drive(_skill("s3b", "surface-ticket"))
    assert _state("s3b") == "fresh"


def test_edit_when_fresh_reminds():
    _drive(_ss("s4"))
    out = _drive(_edit("s4"))
    assert out.strip(), "expected a re-activation note on first modify without load"
    obj = json.loads(out)
    note = obj["hookSpecificOutput"]["additionalContext"]
    assert "task-workflow" in note
    assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert _state("s4") == "reminded"


def test_edit_when_active_is_silent():
    _drive(_ss("s5"))
    _drive(_skill("s5", "task-workflow"))
    assert _drive(_edit("s5")).strip() == ""


def test_reminds_only_once_per_segment():
    _drive(_ss("s6"))
    assert _drive(_edit("s6")).strip(), "first modify reminds"
    assert _drive(_edit("s6")).strip() == "", "second modify is silent"


def test_subagent_is_silent():
    _drive(_ss("s7"))
    assert _drive(_edit("s7", agent_id="sub-123")).strip() == ""


def test_note_is_non_blocking():
    _drive(_ss("s8"))
    obj = json.loads(_drive(_edit("s8")))
    assert "decision" not in obj


def test_out_of_project_write_is_silent_and_keeps_the_nudge_armed():
    # A false nudge on housekeeping would also burn the once-per-segment
    # reminder before the first real project edit (feedback 2026-06-18).
    proj = tempfile.mkdtemp(prefix="tw-proj-")
    outside = os.path.join(tempfile.mkdtemp(prefix="tw-mem-"), "note.md")
    _drive(_ss("s10"))
    out = _drive(_edit("s10", cwd=proj, tool_input={"file_path": outside}))
    assert out.strip() == ""
    assert _state("s10") == "fresh", "out-of-project write must not consume the nudge"
    inside = _drive(_edit("s10", cwd=proj,
                          tool_input={"file_path": os.path.join(proj, "x.py")}))
    assert inside.strip(), "the real in-project edit still gets the reminder"


def test_tmp_write_is_silent():
    proj = tempfile.mkdtemp(prefix="tw-proj-")
    _drive(_ss("s11"))
    out = _drive(_edit("s11", cwd=proj,
                       tool_input={"file_path": "/tmp/tw-scratch/probe.js"}))
    assert out.strip() == ""


def test_in_project_relative_path_reminds():
    proj = tempfile.mkdtemp(prefix="tw-proj-")
    _drive(_ss("s12"))
    out = _drive(_edit("s12", cwd=proj, tool_input={"file_path": "src/app.py"}))
    assert out.strip()


def test_compaction_clears_active_then_reminds():
    _drive(_ss("s9"))
    _drive(_skill("s9", "task-workflow"))
    assert _state("s9") == "active"
    _drive(_ss("s9"))  # a later compaction fires SessionStart again
    assert _state("s9") == "fresh"
    assert _drive(_edit("s9")).strip(), "after compaction, first modify re-reminds"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
