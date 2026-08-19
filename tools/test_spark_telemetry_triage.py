#!/usr/bin/env python3

import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools/spark_telemetry_triage.py"
sys.path.insert(0, str(ROOT / "tools"))
import spark_telemetry_triage


def test_failure_detail_is_bounded_and_actionable():
    detail = spark_telemetry_triage._failure_detail(
        1, '{"type":"error","message":"Reconnecting... stream disconnected before completion"}'
    )
    assert detail == "Spark network transport is unavailable"


def test_adapter_owned_candidate_and_usage():
    work = Path(tempfile.mkdtemp())
    fake = work / "codex"
    fake.write_text(
        "#!/bin/sh\n"
        "out=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '--output-last-message' ]; then out=$2; shift 2; else shift; fi\n"
        "done\n"
        "printf '%s\\n' '{\"evidence\":[],\"candidates\":[]}' > \"$out\"\n"
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
    assert artifact["review_required"] is True
    assert artifact["usage"]["total_tokens"] == 110
    with sqlite3.connect(db) as connection:
        payload = json.loads(connection.execute(
            "SELECT payload FROM events WHERE event='model_usage'"
        ).fetchone()[0])
    assert payload["source"] == "model-lab"
    assert payload["input_tokens"] == 100
    status_value = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_value["status"] == "completed"
    assert status_value["artifact"] == str(artifacts[0])


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK spark telemetry triage - {len(tests)} tests passed")
