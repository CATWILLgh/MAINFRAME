#!/usr/bin/env python3
"""Contract tests for optional Antigravity telemetry auditing."""

from __future__ import annotations

import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKER = ROOT / "adapters/claude-code/dev/model-lab/gemini-telemetry-audit.py"

AUDIT = {
    "summary": "Runtime evidence is narrow.",
    "evidence_quality": {"rating": "low", "reasons": ["One session dominates signals."]},
    "hook_findings": [],
    "capability_signals": [{
        "capability_id": "observability.dev-only-telemetry",
        "support": "partial",
        "reason": "The aggregate contains runtime rows.",
    }],
    "telemetry_gaps": ["No parallel-session evidence."],
    "recommended_next_actions": ["Run a bounded concurrency probe."],
}


def _seed_db(directory: pathlib.Path) -> pathlib.Path:
    db = directory / "telemetry.db"
    script = ROOT / "adapters/claude-code/plugin/hooks/scripts"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import _hooklib; "
        "_hooklib.initialize_telemetry_db(sys.argv[2]); "
        "_hooklib.log_event('user_prompt', {'prompt_len': 7}, "
        "{'session_id':'00000000-0000-0000-0000-000000000001', "
        "'_telemetry_origin':'runtime'})"
    )
    env = dict(os.environ, MAINFRAME_TELEMETRY_DB=str(db), MAINFRAME_TELEMETRY_ORIGIN="runtime")
    subprocess.run([sys.executable, "-c", code, str(script), str(db)], check=True, env=env)
    return db


def _fake_agy(directory: pathlib.Path, result=AUDIT, code=0) -> tuple[pathlib.Path, pathlib.Path]:
    calls = directory / "calls.jsonl"
    binary = directory / "agy"
    wrapper = json.dumps({
        "conversation_id": "test-conversation", "model": "gemini-test",
        "usage": {"total_tokens": 42}, "structured_output": result,
    })
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"p=pathlib.Path({str(calls)!r})\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('1.1.12-test')\n"
        "    raise SystemExit(0)\n"
        "with p.open('a', encoding='utf-8') as h: h.write(json.dumps(sys.argv[1:])+'\\n')\n"
        f"print({wrapper!r})\n"
        f"sys.exit({code})\n",
        encoding="utf-8",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary, calls


def _run(db: pathlib.Path, lab: pathlib.Path, agy: pathlib.Path):
    catalog = lab.parent / "catalog.json"
    catalog.write_text(json.dumps({
        "capabilities": [{
            "id": "observability.dev-only-telemetry",
            "outcome": "Collect private development telemetry.",
            "acceptance": [{"id": "a1", "text": "It is local."}],
        }],
    }), encoding="utf-8")
    env = dict(
        os.environ,
        MAINFRAME_PROJECT_ROOT=str(ROOT),
        MAINFRAME_MODEL_LAB_ROOT=str(lab),
        MAINFRAME_ANTIGRAVITY_BIN=str(agy),
        MAINFRAME_CAPABILITY_CATALOG=str(catalog),
        MAINFRAME_TELEMETRY_DB=str(db),
        MAINFRAME_TELEMETRY_ORIGIN="model-lab",
    )
    return subprocess.run(
        [sys.executable, str(WORKER), "--db", str(db)],
        capture_output=True, text=True, timeout=15, env=env,
    )


def _artifacts(lab: pathlib.Path) -> list[pathlib.Path]:
    return list((lab / "gemini/telemetry-audits").glob("telemetry-*.json"))


def test_valid_audit_is_bounded_and_provenanced():
    directory = pathlib.Path(tempfile.mkdtemp())
    db = _seed_db(directory)
    agy, calls = _fake_agy(directory)
    lab = directory / "lab"
    result = _run(db, lab, agy)
    assert result.returncode == 0 and not result.stdout and not result.stderr
    artifacts = _artifacts(lab)
    assert len(artifacts) == 1
    value = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert value["review_required"] is True and value["audit"] == AUDIT
    assert value["cli"]["version"] == "1.1.12-test"
    assert value["source"]["included_origins"] == ["runtime", "runtime-inferred"]
    assert value["source"]["usable_records"] == 1
    argv = json.loads(calls.read_text(encoding="utf-8").splitlines()[0])
    assert argv[argv.index("--model") + 1] == "gemini-3.7-flash-high"
    assert argv[argv.index("--effort") + 1] == "high"
    assert "--sandbox" in argv and "--disable-slash-commands" in argv
    prompt = argv[argv.index("--print") + 1]
    assert '"included_origins":["runtime","runtime-inferred"]' in prompt
    assert "Return concise English" in prompt


def test_same_snapshot_is_deduplicated():
    directory = pathlib.Path(tempfile.mkdtemp())
    db = _seed_db(directory)
    agy, calls = _fake_agy(directory)
    lab = directory / "lab"
    assert _run(db, lab, agy).returncode == 0
    assert _run(db, lab, agy).returncode == 0
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1


def test_model_failure_leaves_private_retry_metadata_only():
    directory = pathlib.Path(tempfile.mkdtemp())
    db = _seed_db(directory)
    agy, _ = _fake_agy(directory, code=1)
    lab = directory / "lab"
    result = _run(db, lab, agy)
    assert result.returncode == 0 and not result.stdout and not result.stderr
    assert _artifacts(lab) == []
    pending = list((lab / "gemini/telemetry-audits").glob("pending-*.json"))
    assert len(pending) == 1
    value = json.loads(pending[0].read_text(encoding="utf-8"))
    assert value["status"] == "pending" and "source_sha256" in value
    assert "stderr" not in value and "stdout" not in value


def test_unknown_capability_is_rejected():
    directory = pathlib.Path(tempfile.mkdtemp())
    db = _seed_db(directory)
    invalid = dict(AUDIT)
    invalid["capability_signals"] = [{
        "capability_id": "invented.capability", "support": "strong", "reason": "No.",
    }]
    agy, _ = _fake_agy(directory, result=invalid)
    lab = directory / "lab"
    result = _run(db, lab, agy)
    assert result.returncode == 0 and _artifacts(lab) == []


def test_malformed_nested_finding_is_rejected():
    directory = pathlib.Path(tempfile.mkdtemp())
    db = _seed_db(directory)
    invalid = dict(AUDIT)
    invalid["hook_findings"] = [{
        "hook": "example.py", "severity": "urgent", "finding": "Maybe.",
        "evidence": [], "next_test": "Probe it.",
    }]
    agy, _ = _fake_agy(directory, result=invalid)
    lab = directory / "lab"
    result = _run(db, lab, agy)
    assert result.returncode == 0 and _artifacts(lab) == []


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok {test.__name__}")
    print(f"OK Gemini telemetry audit — {len(tests)} tests passed")


if __name__ == "__main__":
    main()
