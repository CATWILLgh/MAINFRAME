#!/usr/bin/env python3
"""Unit tests for the concise-reminder Stop hook (`concise-reminder.py`).

Run: `python3 tools/test_concise_reminder.py` (exit 0 = pass). Stdlib only.
Covers the testable seams: the every-N fire decision, the per-session turn
counter (with an injected state dir), the SessionStart reset, and the
last-assistant-reply length extractor over a synthetic transcript.
"""

import importlib.util
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "adapters/claude-code/plugin", "hooks", "scripts",
                       "concise-reminder.py")
spec = importlib.util.spec_from_file_location("concise_reminder", _SCRIPT)
concise_reminder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(concise_reminder)


def test_fires_only_every_n_turns():
    assert concise_reminder.should_remind(0, 8) is False   # warmup, never at 0
    assert concise_reminder.should_remind(7, 8) is False   # not yet
    assert concise_reminder.should_remind(8, 8) is True    # first fire
    assert concise_reminder.should_remind(9, 8) is False   # silent between
    assert concise_reminder.should_remind(16, 8) is True   # second fire


def test_advance_increments_and_fires_every_n():
    count, last = 0, 0
    seq = []
    for _ in range(9):                              # turns 1..9, n=4
        count, last, ts, reminded = concise_reminder._advance(count, last, 4)
        seq.append((ts, reminded))
    assert [r for _, r in seq] == [False, False, False, True,
                                   False, False, False, True, False]
    assert [ts for ts, _ in seq] == [1, 2, 3, 4, 1, 2, 3, 4, 1]


def test_advance_fire_turn_is_untreated_max_distance():
    # Stop fires after the reply, so the fire-turn reply predates the nudge:
    # it must read as max distance (n), and the first treated reply is next at 1.
    count, last, ts, reminded = concise_reminder._advance(7, 0, 8)   # turn 8
    assert (count, ts, reminded) == (8, 8, True)
    count, last, ts, reminded = concise_reminder._advance(count, last, 8)  # turn 9
    assert (count, ts, reminded) == (9, 1, False)


def test_state_roundtrip_and_reset():
    d = tempfile.mkdtemp()
    p = concise_reminder._counter_path("sess-A", state_dir=d)
    concise_reminder._save(p, 5, 4)
    assert concise_reminder._load(p) == (5, 4)
    concise_reminder._reset(p)
    assert concise_reminder._load(p) == (0, 0)


def test_state_is_per_session_and_defaults():
    d = tempfile.mkdtemp()
    a = concise_reminder._counter_path("sess-A", state_dir=d)
    b = concise_reminder._counter_path("sess-B", state_dir=d)
    assert a != b
    assert concise_reminder._load(a) == (0, 0)     # absent -> default
    concise_reminder._save(a, 3, 0)
    assert concise_reminder._load(b) == (0, 0)     # B unaffected by A


def test_env_overrides_the_interval():
    saved = os.environ.get("MAINFRAME_CONCISE_REMINDER_EVERY")
    try:
        os.environ["MAINFRAME_CONCISE_REMINDER_EVERY"] = "3"
        assert concise_reminder._every() == 3
        os.environ["MAINFRAME_CONCISE_REMINDER_EVERY"] = "garbage"
        assert concise_reminder._every() == concise_reminder.REMINDER_EVERY_N
        del os.environ["MAINFRAME_CONCISE_REMINDER_EVERY"]
        assert concise_reminder._every() == concise_reminder.REMINDER_EVERY_N
    finally:
        if saved is None:
            os.environ.pop("MAINFRAME_CONCISE_REMINDER_EVERY", None)
        else:
            os.environ["MAINFRAME_CONCISE_REMINDER_EVERY"] = saved


def _transcript(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")


def test_last_assistant_chars_sums_text_blocks():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.jsonl")
    _transcript(p, [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "early"},
            {"type": "tool_use", "id": "x", "name": "Read", "input": {}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "x"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "final answer"},      # 12 chars
            {"type": "tool_use", "id": "y", "name": "Bash", "input": {}}]}},
    ])
    assert concise_reminder.last_assistant_chars(p) == len("final answer")


def test_last_assistant_chars_handles_string_content():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.jsonl")
    _transcript(p, [
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": "plain string reply"}},
    ])
    assert concise_reminder.last_assistant_chars(p) == len("plain string reply")


def test_last_assistant_chars_missing_or_garbage_is_none():
    assert concise_reminder.last_assistant_chars("/no/such/file") is None
    d = tempfile.mkdtemp()
    p = os.path.join(d, "empty.jsonl")
    open(p, "w").close()
    assert concise_reminder.last_assistant_chars(p) is None


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print(f"OK concise-reminder — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
