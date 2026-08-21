#!/usr/bin/env python3

import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools/spark_telemetry_triage.py"
sys.path.insert(0, str(ROOT / "tools"))
import spark_telemetry_triage  # noqa: E402


def test_failure_detail_is_bounded_and_actionable():
    detail = spark_telemetry_triage._failure_detail(
        1, '{"type":"error","message":"Reconnecting... stream disconnected before completion"}'
    )
    assert detail == "Spark network transport is unavailable"


def test_candidate_requires_real_exact_evidence_and_references():
    payload = {"records": 7, "nested": {"state": "observed"}}
    valid = {
        "evidence": [
            {"path": "/records", "value": 7},
            {"path": "/nested/state", "value": "observed"},
        ],
        "candidates": [{
            "category": "data-gap",
            "hypothesis": "A bounded gap may exist.",
            "evidence_paths": ["/records"],
            "confidence": "low",
            "next_probe": "Inspect the missing deterministic counter.",
        }],
    }
    assert spark_telemetry_triage._valid_candidate(valid, payload)

    request = {"candidates": valid["candidates"]}
    assert spark_telemetry_triage._candidate_request_error(request, payload) is None
    assert spark_telemetry_triage._materialize_candidate(request, payload) == {
        "evidence": [{"path": "/records", "value": 7}],
        "candidates": valid["candidates"],
    }

    broken = json.loads(json.dumps(valid))
    broken["evidence"][0]["path"] = "/missing"
    assert not spark_telemetry_triage._valid_candidate(broken, payload)
    assert "does not resolve" in spark_telemetry_triage._candidate_error(broken, payload)

    broken = json.loads(json.dumps(valid))
    broken["evidence"][0]["value"] = 8
    assert not spark_telemetry_triage._valid_candidate(broken, payload)

    assert spark_telemetry_triage._merge_usage(
        {"input_tokens": 10, "output_tokens": 2},
        {"input_tokens": 5, "output_tokens": 3},
    ) == {"input_tokens": 15, "output_tokens": 5}

    broken = json.loads(json.dumps(valid))
    broken["candidates"][0]["evidence_paths"] = ["/nested/state"]
    broken["evidence"] = broken["evidence"][:1]
    assert not spark_telemetry_triage._valid_candidate(broken, payload)


def test_source_excludes_model_lab_rows():
    captured = {}

    class FakeTelemetry:
        @staticmethod
        def default_db_path(adapter):
            return Path("/tmp/mainframe-telemetry.db")

        @staticmethod
        def build_report(db, **kwargs):
            captured.update(kwargs)
            return {
                "usable_records": 1,
                "sessions": 1,
                "generated_at": "2026-08-21T00:00:00Z",
                "first_timestamp": "2026-08-20T00:00:00Z",
                "last_timestamp": "2026-08-21T00:00:00Z",
                "token_usage": {"evidence": "runtime", "total": 0},
                "harness_context_cost": {},
                "hook_effectiveness": [],
            }

    with patch.object(spark_telemetry_triage, "_load", return_value=FakeTelemetry):
        source = spark_telemetry_triage._source("codex", None)

    assert source["adapter_id"] == "codex"
    assert captured["included_origins"] == {"runtime", "runtime-inferred"}
    assert captured["recent_limit"] == 0


def test_adapter_owned_candidate_and_usage():
    work = Path(tempfile.mkdtemp())
    fake = work / "codex"
    fake.write_text(
        "#!/bin/sh\n"
        "out=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '--output-last-message' ]; then out=$2; shift 2; else shift; fi\n"
        "done\n"
        "printf '%s\\n' '{\"candidates\":[]}' > \"$out\"\n"
        "printf '%s\\n' '{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":100,\"cached_input_tokens\":20,\"output_tokens\":10,\"reasoning_output_tokens\":2}}'\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    db = work / "telemetry.db"
    output = work / "runtime"
    status_file = work / "status.json"
    env = dict(os.environ, MAINFRAME_CODEX_BIN=str(fake))
    proc = subprocess.run([
        sys.executable, str(SCRIPT), "--adapter", "codex", "--db", str(db),
        "--output-root", str(output), "--status-file", str(status_file),
    ], env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    artifacts = list((output / "codex/model-lab/spark/telemetry-triage").glob("*.json"))
    assert len(artifacts) == 1
    artifact = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact["analyzer_version"] == 5
    assert artifact["provider"] == "openai"
    assert artifact["review_required"] is True
    assert artifact["usage"]["total_tokens"] == 110
    with sqlite3.connect(db) as connection:
        raw_payload, origin = connection.execute(
            "SELECT payload, origin FROM events WHERE event='model_usage'"
        ).fetchone()
        payload = json.loads(raw_payload)
    assert payload["source"] == "model-lab"
    assert origin == "model-lab"
    assert payload["input_tokens"] == 100
    status_value = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_value["status"] == "completed"
    assert status_value["artifact"] == str(artifacts[0])

    repeated = subprocess.run([
        sys.executable, str(SCRIPT), "--adapter", "codex", "--db", str(db),
        "--output-root", str(output), "--status-file", str(status_file),
    ], env=env, capture_output=True, text=True)
    assert repeated.returncode == 0, repeated.stderr
    assert len(list((output / "codex/model-lab/spark/telemetry-triage").glob("*.json"))) == 1
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM events WHERE event='model_usage'"
        ).fetchone()[0] == 1


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK spark telemetry triage - {len(tests)} tests passed")
