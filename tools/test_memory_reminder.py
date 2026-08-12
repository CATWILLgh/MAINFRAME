#!/usr/bin/env python3
"""Tier-1 tests for the main-session, token-based memory reminder."""

import importlib.util
import io
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(
    HERE, "..", "adapters/claude-code/plugin", "hooks", "scripts", "memory-reminder.py")


def _load():
    spec = importlib.util.spec_from_file_location("memory_reminder", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load()


def _row(tokens):
    return {
        "type": "assistant",
        "message": {"usage": {
            "input_tokens": 2,
            "cache_creation_input_tokens": 998,
            "cache_read_input_tokens": tokens - 1_000,
        }},
    }


def _compact(uuid="compact-1"):
    return {"type": "system", "subtype": "compact_boundary", "uuid": uuid}


def _append(path, *rows):
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _drive(payload, reached=(300_000, 301_000), with_session=True):
    if with_session:
        payload = {"session_id": "session-main", **payload}
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout, gate._reached_milestone, gate.log_hook_signal)
    logged = []
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stdout = out
        gate._reached_milestone = lambda p: reached
        gate.log_hook_signal = lambda *a, **k: logged.append((a, k))
        gate.main()
    finally:
        sys.stdin, sys.stdout, gate._reached_milestone, gate.log_hook_signal = saved
    return out.getvalue(), logged


def test_fires_on_new_context_milestone():
    out, logged = _drive({"cwd": "/p", "transcript_path": "/t"})
    obj = json.loads(out)
    note = obj["hookSpecificOutput"]["additionalContext"]
    assert "native auto-memory" in note
    assert "MEMORY.md" in note
    assert obj["hookSpecificOutput"]["hookEventName"] == "Stop"
    args, kwargs = logged[0]
    assert args[1:4] == ("memory-checkpoint", "noted", 1)
    assert kwargs["context"] == gate.MEMORY_NOTE


def test_note_is_non_blocking_and_has_no_feedback_instruction():
    out, _ = _drive({"cwd": "/p", "transcript_path": "/t"})
    obj = json.loads(out)
    assert "decision" not in obj
    assert "harness-feedback" not in out


def test_silent_without_new_milestone():
    out, logged = _drive({"cwd": "/p", "transcript_path": "/t"}, reached=None)
    assert out == ""
    assert logged == []


def test_silent_when_stop_hook_active():
    out, logged = _drive({"cwd": "/p", "stop_hook_active": True})
    assert out == ""
    assert logged == []


def test_silent_inside_subagent():
    out, logged = _drive({
        "cwd": "/p", "transcript_path": "/t", "agent_id": "agent-123",
    })
    assert out == ""
    assert logged == []


def test_silent_without_session_id():
    out, logged = _drive(
        {"cwd": "/p", "transcript_path": "/t"}, with_session=False)
    assert out == ""
    assert logged == []


def test_fail_safe_on_garbage_stdin():
    out = io.StringIO()
    saved = (sys.stdin, sys.stdout)
    try:
        sys.stdin = io.StringIO("not json {{{")
        sys.stdout = out
        gate.main()
    finally:
        sys.stdin, sys.stdout = saved
    assert out.getvalue() == ""


def test_usage_tokens_sum_input_and_cache_fields():
    assert gate._usage_tokens(_row(345_678)) == 345_678
    assert gate._usage_tokens({}) is None
    assert gate._usage_tokens({"message": {"usage": {"input_tokens": "bad"}}}) is None


def test_milestones_are_once_each_and_incremental():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        payload = {"session_id": "s", "transcript_path": transcript}
        _append(transcript, _row(299_999))
        assert gate._reached_milestone(payload, d) is None
        _append(transcript, _row(300_001))
        assert gate._reached_milestone(payload, d) == (300_000, 300_001)
        assert gate._reached_milestone(payload, d) is None
        _append(transcript, _row(600_001))
        assert gate._reached_milestone(payload, d) == (600_000, 600_001)
        assert gate._reached_milestone(payload, d) is None


def test_jump_over_multiple_milestones_emits_only_once():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        payload = {"session_id": "s", "transcript_path": transcript}
        _append(transcript, _row(950_000))
        assert gate._reached_milestone(payload, d) == (900_000, 950_000)
        assert gate._reached_milestone(payload, d) is None


def test_usage_drop_does_not_repeat_a_milestone():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        payload = {"session_id": "s", "transcript_path": transcript}
        _append(transcript, _row(310_000))
        assert gate._reached_milestone(payload, d) == (300_000, 310_000)
        _append(transcript, _row(120_000), _row(320_000))
        assert gate._reached_milestone(payload, d) is None


def test_compaction_starts_a_new_milestone_sequence():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        payload = {"session_id": "s", "transcript_path": transcript}
        _append(transcript, _row(310_000))
        assert gate._reached_milestone(payload, d) == (300_000, 310_000)
        _append(transcript, _compact(), _row(20_000))
        assert gate._reached_milestone(payload, d) is None
        _append(transcript, _row(305_000))
        assert gate._reached_milestone(payload, d) == (300_000, 305_000)


def test_incomplete_trailing_row_is_read_after_completion():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        payload = {"session_id": "s", "transcript_path": transcript}
        encoded = json.dumps(_row(310_000))
        with open(transcript, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        assert gate._reached_milestone(payload, d) is None
        with open(transcript, "a", encoding="utf-8") as handle:
            handle.write("\n")
        assert gate._reached_milestone(payload, d) == (300_000, 310_000)


def test_state_is_isolated_by_session():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        _append(transcript, _row(310_000))
        first = {"session_id": "a", "transcript_path": transcript}
        second = {"session_id": "b", "transcript_path": transcript}
        assert gate._reached_milestone(first, d)
        assert gate._reached_milestone(second, d)


def test_parallel_sessions_keep_independent_state():
    with tempfile.TemporaryDirectory() as d:
        payloads = []
        for index in range(24):
            transcript = os.path.join(d, f"session-{index}.jsonl")
            _append(transcript, _row(310_000 + index))
            payloads.append({
                "session_id": f"parallel-{index}",
                "transcript_path": transcript,
            })
        with ThreadPoolExecutor(max_workers=12) as pool:
            first = list(pool.map(lambda item: gate._reached_milestone(item, d), payloads))
            second = list(pool.map(lambda item: gate._reached_milestone(item, d), payloads))
        assert all(result and result[0] == 300_000 for result in first)
        assert second == [None] * len(payloads)


def test_parallel_same_session_emits_once():
    with tempfile.TemporaryDirectory() as d:
        transcript = os.path.join(d, "session.jsonl")
        _append(transcript, _row(310_000))
        payload = {"session_id": "shared", "transcript_path": transcript}
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda _: gate._reached_milestone(payload, d), range(24)))
        assert len([result for result in results if result is not None]) == 1


if __name__ == "__main__":
    fns = [value for key, value in sorted(globals().items()) if key.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f" FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
