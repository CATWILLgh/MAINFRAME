#!/usr/bin/env python3
"""Tests for the non-blocking ticket filename reminder.

The hyphenated hook script is loaded by path via importlib. main() is driven
with a controlled stdin payload and captured stdout. No real environment.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin", "hooks", "scripts", "ticket-id-format-reminder.py")


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


def _content(ticket_id="2e7c"):
    return f"---\nid: {ticket_id}\n---\n\n# Ticket\n"


def _write(file_path, content=None):
    return {"tool_name": "Write",
            "tool_input": {"file_path": file_path,
                           "content": _content() if content is None else content}}


def test_flags_sequential_ticket():
    out = _drive(_write("docs/tickets/005-foo-bar.md", _content("005")))
    assert out.strip(), "expected a note for a sequential NNN ticket id"
    obj = json.loads(out)
    note = obj["hookSpecificOutput"]["additionalContext"]
    assert "openssl rand -hex 2" in note
    assert "Do not regenerate the ticket body" in note
    assert obj["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def test_note_is_non_blocking():
    obj = json.loads(_drive(_write("docs/tickets/005-foo.md", _content("005"))))
    assert "decision" not in obj, "reminder must not block"


def test_hex_id_passes():
    path = "docs/tickets/open/observations/2e7c-provider-timeout.md"
    assert _drive(_write(path)).strip() == ""


def test_archived_ticket_shape_passes_without_mutation_note():
    path = "docs/tickets/archive/resolved/2e7c-provider-timeout.md"
    assert _drive(_write(path)).strip() == ""


def test_eight_hex_id_is_not_the_new_compact_format():
    assert _drive(_write("docs/tickets/2e7c3147-provider-timeout.md",
                         _content("2e7c3147"))).strip()


def test_frontmatter_id_must_match_filename():
    assert _drive(_write("docs/tickets/2e7c-provider-timeout.md",
                         _content("beef"))).strip()


def test_duplicate_id_across_lifecycle_directories_is_flagged():
    root = tempfile.mkdtemp()
    existing_dir = os.path.join(
        root, "docs", "tickets", "archive", "resolved"
    )
    os.makedirs(existing_dir)
    with open(
        os.path.join(existing_dir, "2e7c-old-provider-timeout.md"),
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(_content())
    payload = _write(
        os.path.join(
            root,
            "docs",
            "tickets",
            "open",
            "observations",
            "2e7c-new-provider-timeout.md",
        )
    )
    payload["cwd"] = root
    out = _drive(payload)
    assert "already belongs to another ticket" in out


def test_slug_must_be_descriptive_kebab_case_shape():
    assert _drive(_write("docs/tickets/2e7c.md", _content())).strip()
    assert _drive(_write("docs/tickets/2e7c-Provider Timeout.md", _content())).strip()


def test_readme_ignored():
    assert _drive(_write("docs/tickets/README.md")).strip() == ""


def test_non_ticket_path_ignored():
    assert _drive(_write("src/005-foo.md")).strip() == ""
    assert _drive(_write("docs/005-foo.md")).strip() == ""


def test_edit_does_not_nag():
    p = {"tool_name": "Edit",
         "tool_input": {"file_path": "docs/tickets/005-foo.md"}}
    assert _drive(p).strip() == ""


def test_registration_runs_only_for_write():
    hooks_path = os.path.join(
        HERE, "..", "adapters", "claude-code", "plugin", "hooks", "hooks.json"
    )
    with open(hooks_path, encoding="utf-8") as handle:
        groups = json.load(handle)["hooks"]["PostToolUse"]
    owners = [
        group.get("matcher")
        for group in groups
        for hook in group.get("hooks", [])
        if hook.get("args", [""])[-1].endswith("ticket-id-format-reminder.py")
    ]
    assert owners == ["Write"]


def test_missing_file_path_safe():
    assert _drive({"tool_name": "Write", "tool_input": {}}).strip() == ""


def test_absolute_path_flagged():
    out = _drive(_write("/Users/x/proj/docs/tickets/038-baz.md", _content("038")))
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
