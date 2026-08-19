#!/usr/bin/env python3
"""Create a cheap, review-only Spark triage of one adapter's safe telemetry."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-5.3-codex-spark"
EFFORT = "low"
ANALYZER_VERSION = 3


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source(adapter: str, db: Path | None):
    telemetry = _load(ROOT / "tools/telemetry_data.py", "mainframe_telemetry_data")
    if db is None:
        db = telemetry.default_db_path(adapter)
    report = telemetry.build_report(db, adapter_id=adapter, recent_limit=0)
    return {
        "adapter_id": adapter,
        "records": report["usable_records"],
        "sessions": report["sessions"],
        "token_usage": report["token_usage"],
        "harness_context_cost": report["harness_context_cost"],
        "hook_effectiveness": report["hook_effectiveness"],
        "measurement_boundaries": {
            "injected_token_count": "estimated-range",
            "runtime_token_count": report["token_usage"]["evidence"],
            "causal_overhead": "unproven",
            "cost_or_savings": "requires-comparable-ab-runs",
        },
    }


def _usage(stdout: str):
    latest = None
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "turn.completed" or not isinstance(row.get("usage"), dict):
            continue
        raw = row["usage"]
        latest = {
            "input_tokens": int(raw.get("input_tokens", 0)),
            "cached_input_tokens": int(raw.get("cached_input_tokens", 0)),
            "cache_write_tokens": int(raw.get("cache_write_input_tokens", 0)),
            "output_tokens": int(raw.get("output_tokens", 0)),
            "reasoning_output_tokens": int(raw.get("reasoning_output_tokens", 0)),
        }
        latest["total_tokens"] = latest["input_tokens"] + latest["output_tokens"]
    return latest


def _pointer(payload: object, path: str) -> object:
    if not isinstance(path, str) or not path.startswith("/"):
        raise KeyError(path)
    current = payload
    for raw in path[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(path)
    return current


def _candidate_error(value, payload) -> str | None:
    if not isinstance(value, dict) or set(value) != {"evidence", "candidates"}:
        return "top-level shape is invalid"
    evidence = value["evidence"]
    candidates = value["candidates"]
    if not isinstance(evidence, list) or len(evidence) > 12:
        return "evidence list is invalid"
    if not isinstance(candidates, list) or len(candidates) > 8:
        return "candidate list is invalid"
    evidence_paths = set()
    for row in evidence:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "value"}
            or not isinstance(row["path"], str)
            or row["path"] in evidence_paths
        ):
            return "evidence row shape or path uniqueness is invalid"
        try:
            expected = _pointer(payload, row["path"])
        except (KeyError, IndexError, ValueError, TypeError):
            return "an evidence path does not resolve in the input"
        if isinstance(expected, (dict, list)) or row["value"] != expected:
            return "an evidence value does not exactly match its input primitive"
        evidence_paths.add(row["path"])
    categories = {"noisy-injection", "model-lab-cost", "hook-efficiency", "data-gap"}
    for row in candidates:
        if not isinstance(row, dict) or set(row) != {
            "category", "hypothesis", "evidence_paths", "confidence", "next_probe"
        }:
            return "candidate row shape is invalid"
        if row["category"] not in categories or row["confidence"] not in {"low", "medium"}:
            return "candidate category or confidence is invalid"
        if not isinstance(row["hypothesis"], str) or not row["hypothesis"].strip():
            return "candidate hypothesis is empty"
        if not isinstance(row["next_probe"], str) or not row["next_probe"].strip():
            return "candidate probe is empty"
        if not isinstance(row["evidence_paths"], list) or not row["evidence_paths"]:
            return "candidate evidence paths are empty"
        if (
            len(set(row["evidence_paths"])) != len(row["evidence_paths"])
            or not set(row["evidence_paths"]).issubset(evidence_paths)
        ):
            return "candidate references evidence that was not returned exactly"
    return None


def _valid_candidate(value, payload) -> bool:
    return _candidate_error(value, payload) is None


def _candidate_request_error(value, payload) -> str | None:
    if not isinstance(value, dict) or set(value) != {"candidates"}:
        return "top-level shape is invalid"
    candidates = value["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 8:
        return "candidate list is invalid"
    categories = {"noisy-injection", "model-lab-cost", "hook-efficiency", "data-gap"}
    cited_paths = set()
    for row in candidates:
        if not isinstance(row, dict) or set(row) != {
            "category", "hypothesis", "evidence_paths", "confidence", "next_probe"
        }:
            return "candidate row shape is invalid"
        if row["category"] not in categories or row["confidence"] not in {"low", "medium"}:
            return "candidate category or confidence is invalid"
        if not isinstance(row["hypothesis"], str) or not row["hypothesis"].strip():
            return "candidate hypothesis is empty"
        if not isinstance(row["next_probe"], str) or not row["next_probe"].strip():
            return "candidate probe is empty"
        paths = row["evidence_paths"]
        if not isinstance(paths, list) or not paths or len(paths) > 6:
            return "candidate evidence paths are invalid"
        if len(set(paths)) != len(paths):
            return "candidate evidence paths are duplicated"
        for path in paths:
            try:
                expected = _pointer(payload, path)
            except (KeyError, IndexError, ValueError, TypeError):
                return "a candidate evidence path does not resolve in the input"
            if isinstance(expected, (dict, list)):
                return "a candidate evidence path does not identify a primitive"
            cited_paths.add(path)
    if len(cited_paths) > 12:
        return "candidates cite more than twelve distinct evidence paths"
    return None


def _materialize_candidate(value, payload) -> dict:
    evidence = []
    seen = set()
    for row in value["candidates"]:
        for path in row["evidence_paths"]:
            if path not in seen:
                evidence.append({"path": path, "value": _pointer(payload, path)})
                seen.add(path)
    return {"evidence": evidence, "candidates": value["candidates"]}


def _merge_usage(total: dict | None, current: dict | None) -> dict | None:
    if current is None:
        return total
    if total is None:
        return dict(current)
    return {key: int(total.get(key, 0)) + int(current.get(key, 0)) for key in current}


def _failure_detail(returncode: int, stdout: str) -> str:
    lowered = stdout.lower()
    if any(marker in lowered for marker in (
        "proxy connection failed", "error sending request",
        "stream disconnected before completion", "reconnecting...",
    )):
        return "Spark network transport is unavailable"
    if "model" in lowered and any(
        marker in lowered for marker in ("not found", "not available", "unknown model")
    ):
        return "Spark model is unavailable for this account or client"
    return f"Spark worker exit {returncode}"


def _record_usage(
    adapter: str, usage: dict | None, digest: str, db: Path | None, request_count: int
):
    if not usage:
        return
    receiver = _load(ROOT / "tools/native_telemetry_receiver.py", "mainframe_receiver")
    sample = {
        "adapter_id": adapter,
        "session_id": "model-lab",
        "model": MODEL,
        "payload": {
            "sample_id": hashlib.sha256(f"spark-triage:{adapter}:{digest}".encode()).hexdigest(),
            "source": "model-lab", "request_count": request_count, **usage,
        },
    }
    paths = _load(
        ROOT / "tools/telemetry_data.py", "mainframe_telemetry_paths"
    ).default_db_paths()
    if db is not None:
        paths[adapter] = db.resolve()
    receiver.record_samples([sample], paths)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, choices=("claude-code", "codex"))
    parser.add_argument("--db", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args(argv)
    def finish(status, detail, artifact=""):
        if args.status_file:
            args.status_file.parent.mkdir(parents=True, exist_ok=True)
            temporary_status = args.status_file.with_suffix(".tmp")
            temporary_status.write_text(json.dumps({
                "status": status, "detail": detail, "artifact": str(artifact),
            }) + "\n", encoding="utf-8")
            os.chmod(temporary_status, 0o600)
            os.replace(temporary_status, args.status_file)
        return 0
    payload = _source(args.adapter, args.db)
    source_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    analysis_digest = hashlib.sha256(
        f"spark-telemetry-triage:{ANALYZER_VERSION}:{source_digest}".encode()
    ).hexdigest()
    output_root = args.output_root or ROOT / "workspace/runtime"
    destination = output_root / args.adapter / "model-lab/spark/telemetry-triage" / f"triage-{analysis_digest[:16]}.json"
    if destination.exists():
        return finish("completed", "matching telemetry was already analyzed", destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    base_prompt = """Analyze this privacy-safe MAINFRAME telemetry summary for cheap triage only.
Return exact JSON Pointer evidence paths. MAINFRAME will copy the cited primitive
values deterministically after validation; do not return a separate evidence list.
Each path is one JSON string. Never join, comma-separate, or combine several paths.
Return bounded hypotheses. Do not claim causal overhead,
waste, savings, or effectiveness from aggregates. Recommend a probe instead.
Do not inspect prompts, code, paths, transcripts, or credentials.\n\n""" + json.dumps(payload, sort_keys=True)
    fd, response_name = tempfile.mkstemp(prefix="mainframe-spark-triage-", suffix=".json")
    os.close(fd)
    usage = None
    request_count = 0
    try:
        prompt = base_prompt
        candidate = None
        error = "Spark returned no review candidate"
        for attempt in range(2):
            proc = subprocess.run([
                os.environ.get("MAINFRAME_CODEX_BIN", "codex"), "exec", "--model", MODEL,
                "--config", f'model_reasoning_effort="{EFFORT}"', "--ephemeral",
                "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only",
                "--cd", str(ROOT), "--output-schema", str(ROOT / "tools/schemas/spark-telemetry-triage.json"),
                "--output-last-message", response_name, "--json", "-",
            ], input=prompt, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
               timeout=180, check=False)
            request_count += 1
            usage = _merge_usage(usage, _usage(proc.stdout))
            if proc.returncode != 0:
                return finish("retryable", _failure_detail(proc.returncode, proc.stdout))
            raw_candidate = json.loads(Path(response_name).read_text(encoding="utf-8"))
            error = _candidate_request_error(raw_candidate, payload)
            if error is None:
                candidate = _materialize_candidate(raw_candidate, payload)
                if not _valid_candidate(candidate, payload):
                    error = "deterministic evidence materialization failed"
                    continue
                break
            if attempt == 0:
                prompt = (
                    base_prompt
                    + "\n\nThe previous JSON was rejected because " + error + ". "
                    + "Return a corrected complete JSON object. Previous JSON:\n"
                    + json.dumps(raw_candidate, ensure_ascii=False, separators=(",", ":"))
                )
        if error is not None:
            return finish("retryable", f"Spark validation failed: {error}")
        envelope = {
            "schema": 1, "analyzer_version": ANALYZER_VERSION,
            "adapter": args.adapter, "producer": "spark-telemetry-triage",
            "provider": "openai", "model": MODEL, "effort": EFFORT,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "source_sha256": source_digest, "usage": usage, "review_required": True,
            "candidate": candidate,
        }
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        return finish("completed", "review candidate stored", destination)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return finish("retryable", f"Spark unavailable: {type(error).__name__}")
    finally:
        _record_usage(args.adapter, usage, analysis_digest, args.db, request_count)
        try:
            os.unlink(response_name)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
