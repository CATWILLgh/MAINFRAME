#!/usr/bin/env python3
"""Contract tests for the dev-only Codex subagent analysis queue."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "adapters/codex/hooks/scripts"
WORKER = ROOT / "adapters/codex/dev/model-lab/gemini-subagent-audit.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


queue = _load("codex_subagent_queue_test", HOOKS / "_subagent_analysis_queue.py")
worker = _load("codex_subagent_worker_test", WORKER)


def _home_fixture():
    directory = tempfile.TemporaryDirectory(dir=Path.home())
    base = Path(directory.name)
    codex = base / ".codex"
    enabled = codex / "mainframe/codex/telemetry/enabled"
    enabled.parent.mkdir(parents=True)
    enabled.touch()
    queue_root = base / "queue"
    transcript = base / "sessions/subagent.jsonl"
    transcript.parent.mkdir()
    rows = [
        {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "PRIVATE SYSTEM INSTRUCTION"}]}},
        {"type": "turn_context", "payload": {"turn_id": "t1", "model": "gpt-5.6-sol", "effort": "high"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": "Implement the parser; api_key=supersecretvalue"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": "Implement the parser; api_key=supersecretvalue"}},
        {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "arguments": "cat protected-secret"}},
        {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Implemented the parser and checks passed."}]}},
        {"type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": "Implementation completed."}},
    ]
    transcript.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return directory, base, codex, queue_root, transcript


def _payload(transcript: Path):
    return {
        "session_id": "session-1", "agent_id": "agent-1",
        "agent_type": "mainframe_python_backend_engineer",
        "model": "gpt-5.6-sol", "agent_transcript_path": str(transcript),
    }


def test_queue_is_dev_only_private_and_idempotent():
    fixture, _base, codex, queue_root, transcript = _home_fixture()
    old = dict(os.environ)
    try:
        os.environ.update(CODEX_HOME=str(codex), MAINFRAME_CODEX_SUBAGENT_QUEUE=str(queue_root))
        assert queue.enqueue(_payload(transcript)) == "queued"
        assert queue.enqueue(_payload(transcript)) == "deduplicated"
        jobs = list((queue_root / "pending").glob("*.json"))
        assert len(jobs) == 1 and stat.S_IMODE(jobs[0].stat().st_mode) == 0o600
        record = json.loads(jobs[0].read_text(encoding="utf-8"))
        assert record["runtime_model"] == "gpt-5.6-sol"
        assert record["runtime_effort"] == "unavailable"
        (codex / "mainframe/codex/telemetry/enabled").unlink()
        assert queue.enqueue({**_payload(transcript), "agent_id": "agent-2"}) == "disabled"
    finally:
        os.environ.clear()
        os.environ.update(old)
        fixture.cleanup()


def test_queue_rejects_missing_identity_and_non_home_transcript():
    fixture, _base, codex, queue_root, transcript = _home_fixture()
    old = dict(os.environ)
    try:
        os.environ.update(CODEX_HOME=str(codex), MAINFRAME_CODEX_SUBAGENT_QUEUE=str(queue_root))
        assert queue.enqueue({**_payload(transcript), "agent_id": ""}) == "ignored"
        outside = Path(tempfile.mkdtemp()) / "outside.jsonl"
        outside.write_text("{}\n", encoding="utf-8")
        assert queue.enqueue(_payload(outside)) == "ignored"
    finally:
        os.environ.clear()
        os.environ.update(old)
        fixture.cleanup()


def test_subagent_stop_hook_enqueues_the_documented_transcript():
    fixture, base, codex, queue_root, transcript = _home_fixture()
    try:
        payload = {
            **_payload(transcript),
            "hook_event_name": "SubagentStop",
            "cwd": str(base),
        }
        result = subprocess.run(
            [sys.executable, str(HOOKS / "mainframe-hook.py")],
            input=json.dumps(payload), text=True, capture_output=True, check=False,
            env={
                **os.environ,
                "CODEX_HOME": str(codex),
                "MAINFRAME_CODEX_SUBAGENT_QUEUE": str(queue_root),
                "MAINFRAME_CODEX_TELEMETRY_DB": str(base / "telemetry.db"),
                "MAINFRAME_CODEX_TELEMETRY_ORIGIN": "synthetic",
            },
        )
        assert result.returncode == 0, result.stderr
        jobs = list((queue_root / "pending").glob("*.json"))
        assert len(jobs) == 1
        assert json.loads(jobs[0].read_text(encoding="utf-8"))["agent_id"] == "agent-1"
    finally:
        fixture.cleanup()


def test_sanitizer_hides_runtime_choice_tool_arguments_and_secret_shapes():
    fixture, _base, _codex, _queue_root, transcript = _home_fixture()
    try:
        value = worker.sanitized_transcript(transcript)
        encoded = json.dumps(value)
        assert "gpt-5.6-sol" not in encoded and '"effort"' not in encoded
        assert "supersecretvalue" not in encoded and "cat protected-secret" not in encoded
        assert "PRIVATE SYSTEM INSTRUCTION" not in encoded
        assert "exec_command" in encoded and "Implemented the parser" in encoded
        assert encoded.count("Implement the parser") == 1
        assert value["turns_observed"] == 1 and value["tool_calls_observed"] == 1
    finally:
        fixture.cleanup()


def test_worker_is_blind_then_reattaches_observed_runtime_metadata():
    fixture, base, codex, queue_root, transcript = _home_fixture()
    old = dict(os.environ)
    try:
        os.environ.update(CODEX_HOME=str(codex), MAINFRAME_CODEX_SUBAGENT_QUEUE=str(queue_root))
        assert queue.enqueue(_payload(transcript)) == "queued"
        calls = base / "calls.json"
        fake = base / "agy"
        result = {
            "task": "Implement a parser.", "complexity": "medium",
            "work_type": "implementation", "outcome": "completed",
            "execution": {"turns": 1, "tool_calls": 1, "repeated_actions": 0, "assessment": "efficient"},
            "evidence": ["The request asks for a parser and the final message reports completion."],
            "limitations": ["Tool arguments and results were intentionally omitted."],
        }
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            f"pathlib.Path({str(calls)!r}).write_text(json.dumps(sys.argv[1:]))\n"
            f"print(json.dumps({{'structured_output': {result!r}, 'model':'gemini-test','usage':{{'total_tokens':42}}}}))\n",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["MAINFRAME_ANTIGRAVITY_BIN"] = str(fake)
        telemetry_db = base / "telemetry.db"
        os.environ["MAINFRAME_CODEX_TELEMETRY_DB"] = str(telemetry_db)
        claimed = worker.claim_next(queue_root)
        assert claimed is not None
        status, artifact = worker.process(claimed, ROOT)
        assert status == "completed"
        prompt_args = json.loads(calls.read_text(encoding="utf-8"))
        prompt = prompt_args[prompt_args.index("--print") + 1]
        assert "gpt-5.6-sol" not in prompt and "supersecretvalue" not in prompt
        envelope = json.loads(Path(artifact).read_text(encoding="utf-8"))
        assert envelope["runtime"] == {
            "model": "gpt-5.6-sol", "effort": "unavailable",
            "effort_evidence": "Codex hook input has no documented effort field",
        }
        connection = sqlite3.connect(telemetry_db)
        try:
            origin, usage = connection.execute(
                "SELECT origin, payload FROM events WHERE event = 'model_usage'"
            ).fetchone()
        finally:
            connection.close()
        assert origin == "model-lab"
        assert json.loads(usage)["total_tokens"] == 42
        Path(artifact).unlink()
    finally:
        os.environ.clear()
        os.environ.update(old)
        fixture.cleanup()


def test_failed_worker_keeps_job_for_bounded_retry():
    fixture, base, codex, queue_root, transcript = _home_fixture()
    old = dict(os.environ)
    try:
        os.environ.update(CODEX_HOME=str(codex), MAINFRAME_CODEX_SUBAGENT_QUEUE=str(queue_root))
        assert queue.enqueue(_payload(transcript)) == "queued"
        fake = base / "agy-fail"
        fake.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["MAINFRAME_ANTIGRAVITY_BIN"] = str(fake)
        claimed = worker.claim_next(queue_root)
        status, artifact = worker.process(claimed, ROOT)
        assert status == "retryable" and artifact == ""
        jobs = list((queue_root / "pending").glob("*.json"))
        assert len(jobs) == 1
        record = json.loads(jobs[0].read_text(encoding="utf-8"))
        assert record["attempts"] == 1 and record["status"] == "queued"
    finally:
        os.environ.clear()
        os.environ.update(old)
        fixture.cleanup()


def test_stale_processing_job_is_recovered():
    fixture, _base, codex, queue_root, transcript = _home_fixture()
    old = dict(os.environ)
    try:
        os.environ.update(CODEX_HOME=str(codex), MAINFRAME_CODEX_SUBAGENT_QUEUE=str(queue_root))
        assert queue.enqueue(_payload(transcript)) == "queued"
        pending = next((queue_root / "pending").glob("*.json"))
        processing = queue_root / "processing"
        processing.mkdir()
        stale = processing / (pending.stem + ".processing")
        pending.replace(stale)
        old_time = time.time() - worker.STALE_PROCESSING_SECONDS - 1
        os.utime(stale, (old_time, old_time))
        claimed = worker.claim_next(queue_root)
        assert claimed is not None and claimed.name == stale.name
    finally:
        os.environ.clear()
        os.environ.update(old)
        fixture.cleanup()


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK Codex subagent analysis — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
