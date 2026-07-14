#!/usr/bin/env python3
"""Tier-1 tests for ticket-id-format-reminder.py (PostToolUse NNN->hex nudge).

The hyphenated hook script is loaded by path via importlib. main() is driven
with a controlled stdin payload and captured stdout. No real environment.
"""

import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "dist", "claude-code", "plugin", "hooks", "scripts", "ticket-id-format-reminder.py")


def _load():
    spec = importlib.util.spec_from_file_location("ticket_id_format", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load()


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


def _write(file_path):
    return {"tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": "x"}}


def test_flags_sequential_ticket():
    out = _drive(_write("docs/tickets/005-foo-bar.md"))
    assert out.strip(), "expected a note for a sequential NNN ticket id"
    obj = json.loads(out)
    note = obj["hookSpecificOutput"]["additionalContext"]
    assert "openssl rand -hex 4" in note
    assert obj["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def test_note_is_non_blocking():
    obj = json.loads(_drive(_write("docs/tickets/005-foo.md")))
    assert "decision" not in obj, "reminder must not block"


def test_hex_id_passes():
    assert _drive(_write("docs/tickets/2e7c3147-foo.md")).strip() == ""


def test_eight_digit_id_passes():
    # 8 all-decimal chars is a valid hex-shaped token, not NNN.
    assert _drive(_write("docs/tickets/12345678-foo.md")).strip() == ""


def test_readme_ignored():
    assert _drive(_write("docs/tickets/README.md")).strip() == ""


def test_non_ticket_path_ignored():
    assert _drive(_write("src/005-foo.md")).strip() == ""
    assert _drive(_write("docs/005-foo.md")).strip() == ""


def test_edit_does_not_nag():
    p = {"tool_name": "Edit",
         "tool_input": {"file_path": "docs/tickets/005-foo.md"}}
    assert _drive(p).strip() == ""


def test_missing_file_path_safe():
    assert _drive({"tool_name": "Write", "tool_input": {}}).strip() == ""


def test_absolute_path_flagged():
    out = _drive(_write("/Users/x/proj/docs/tickets/038-baz.md"))
    assert out.strip(), "expected a note for an absolute-path NNN ticket"


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
