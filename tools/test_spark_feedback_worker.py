#!/usr/bin/env python3
"""Contract tests for the detached Spark feedback analysis worker."""

import json
import os
import pathlib
import sqlite3
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKER = ROOT / "adapters/claude-code/dev/model-lab/spark-feedback-worker.py"

CANDIDATE = {
    "summary": "The report maps to a narrow permission regression.",
    "evidence": [{"location": "adapters/claude-code/install.sh", "observation": "The relevant adapter owns the behavior."}],
    "recommended_test": {
        "name": "test_reported_permission_case",
        "purpose": "Preserve the reported legitimate command.",
        "setup": ["Create an isolated home."],
        "action": ["Run the classifier."],
        "assertions": ["The legitimate command is not denied."],
    },
    "confidence": "medium",
    "limitations": ["No live Claude runtime was invoked."],
}


def _feedback(directory, schema=2):
    path = directory / "feedback.md"
    path.write_text(
        "---\n"
        f"schema: {schema}\n"
        "adapter: claude-code\n"
        "model_lab_eligible: true\n"
        "session: sess-1\n"
        "---\n\n# Example\n\n## Trigger\nA deterministic trigger.\n",
        encoding="utf-8",
    )
    return path


def _fake_codex(directory, response=CANDIDATE, code=0):
    calls = directory / "calls.jsonl"
    script = directory / "codex"
    payload = json.dumps(response)
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"calls = pathlib.Path({str(calls)!r})\n"
        "with calls.open('a', encoding='utf-8') as h:\n"
        "    h.write(json.dumps({'argv': sys.argv[1:], 'stdin': sys.stdin.read()}) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "if '--output-last-message' in args:\n"
        f"    pathlib.Path(args[args.index('--output-last-message') + 1]).write_text({payload!r}, encoding='utf-8')\n"
        f"sys.exit({code})\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script, calls


def _run(feedback, model_root, codex, telemetry_db=None):
    env = dict(
        os.environ,
        MAINFRAME_PROJECT_ROOT=str(ROOT),
        MAINFRAME_MODEL_LAB_ROOT=str(model_root),
        MAINFRAME_CODEX_BIN=str(codex),
    )
    if telemetry_db:
        env["MAINFRAME_TELEMETRY_DB"] = str(telemetry_db)
    return subprocess.run(
        [sys.executable, str(WORKER), str(feedback)],
        capture_output=True, text=True, timeout=10, env=env,
    )


def _artifacts(model_root):
    return list((model_root / "spark/hook-regression-candidates").glob("*.json"))


def test_valid_result_has_trusted_envelope_and_exact_invocation():
    d = pathlib.Path(tempfile.mkdtemp())
    feedback = _feedback(d)
    codex, calls = _fake_codex(d)
    db = d / "telemetry/telemetry.db"
    result = _run(feedback, d / "lab", codex, db)
    assert result.returncode == 0 and not result.stdout and not result.stderr
    artifacts = _artifacts(d / "lab")
    assert len(artifacts) == 1
    value = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert value["adapter"] == "claude-code"
    assert value["model"] == "gpt-5.3-codex-spark"
    assert value["effort"] == "medium"
    assert value["candidate"] == CANDIDATE
    assert len(value["source"]["sha256"]) == 64
    call = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
    argv = call["argv"]
    for token in ("exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "read-only", "--output-schema"):
        assert token in argv, argv
    assert 'model_reasoning_effort="medium"' in argv
    assert str(feedback) in call["stdin"]
    con = sqlite3.connect(db)
    try:
        event, payload = con.execute(
            "SELECT event, payload FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    assert event == "model_lab"
    assert json.loads(payload)["status"] == "completed"


def test_same_feedback_is_deduplicated():
    d = pathlib.Path(tempfile.mkdtemp())
    feedback = _feedback(d)
    codex, calls = _fake_codex(d)
    model_root = d / "lab"
    assert _run(feedback, model_root, codex).returncode == 0
    assert _run(feedback, model_root, codex).returncode == 0
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1
    assert len(_artifacts(model_root)) == 1


def test_failed_or_invalid_model_is_quiet_and_leaves_no_artifact():
    for response, code in ((CANDIDATE, 1), ({"summary": "incomplete"}, 0)):
        d = pathlib.Path(tempfile.mkdtemp())
        feedback = _feedback(d)
        codex, _ = _fake_codex(d, response=response, code=code)
        result = _run(feedback, d / "lab", codex)
        assert result.returncode == 0 and not result.stdout and not result.stderr
        assert _artifacts(d / "lab") == []


def test_legacy_feedback_is_ignored_without_model_call():
    d = pathlib.Path(tempfile.mkdtemp())
    feedback = _feedback(d, schema=1)
    codex, calls = _fake_codex(d)
    result = _run(feedback, d / "lab", codex)
    assert result.returncode == 0
    assert not calls.exists()
    assert not (d / "lab").exists()


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK spark feedback worker — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
