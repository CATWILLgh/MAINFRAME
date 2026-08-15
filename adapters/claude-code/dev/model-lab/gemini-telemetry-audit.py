#!/usr/bin/env python3
"""Run one optional Antigravity audit over privacy-safe Claude telemetry.

The worker is deliberately outside the hook path. It treats Gemini output as a
review queue, never as capability evidence or an automatic configuration
decision.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

MODEL = "gemini-3.7-flash-high"
EFFORT = "high"
TASK = "telemetry-audit"
OUTPUT_SCHEMA = 1
TIMEOUT_SECONDS = 360
RUNTIME_ORIGINS = {"runtime", "runtime-inferred"}


def _repo_root() -> pathlib.Path:
    override = os.environ.get("MAINFRAME_PROJECT_ROOT")
    return pathlib.Path(override).resolve() if override else pathlib.Path(__file__).resolve().parents[4]


def _output_dir(root: pathlib.Path) -> pathlib.Path:
    override = os.environ.get("MAINFRAME_MODEL_LAB_ROOT")
    base = pathlib.Path(override).resolve() if override else root / "workspace" / "runtime" / "claude-code" / "model-lab"
    return base / "gemini" / "telemetry-audits"


def _load_tools(root: pathlib.Path):
    tools = root / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import telemetry_data
    return telemetry_data


def _read_capabilities(root: pathlib.Path) -> list[dict]:
    override = os.environ.get("MAINFRAME_CAPABILITY_CATALOG")
    path = pathlib.Path(override).resolve() if override else root / ".agents" / "adapter-capabilities" / "catalog.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for item in value.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        rows.append({
            "id": item.get("id", ""),
            "outcome": item.get("outcome", ""),
            "acceptance": item.get("acceptance", []),
        })
    return rows


def _source_payload(root: pathlib.Path, db: pathlib.Path) -> dict:
    telemetry_data = _load_tools(root)
    report = telemetry_data.build_report(
        db, recent_limit=0, included_origins=RUNTIME_ORIGINS
    )
    # Keep the model input and deduplication key independent from synthetic,
    # model-lab, and unclassified rows that share the physical database.
    telemetry = {
        key: report[key]
        for key in (
            "active", "format_version", "usable_records", "sessions",
            "agent_instances", "first_timestamp", "last_timestamp", "last_id",
            "included_origins", "event_counts", "by_day", "by_agent",
            "agent_lifecycle", "breakdowns", "hook_effectiveness", "error",
        )
    }
    return {
        "telemetry": telemetry,
        "known_capabilities": _read_capabilities(root),
        "limits": {
            "scope": "Aggregate, privacy-safe Claude Code adapter telemetry only.",
            "not_evidence": "Model conclusions are candidates for independent verification, not capability proof.",
            "historical_origin": "runtime-inferred means a legacy row matched the Claude UUID session shape; it was not rewritten.",
        },
    }


def _prompt(payload: dict) -> str:
    return """You are auditing MAINFRAME's Claude Code adapter telemetry.

Analyze only the JSON supplied below. Do not browse, inspect other files, run
commands, or infer behavior absent from the aggregates. Return exactly the
supplied JSON schema.

Rules:
- Return concise English in every free-text field.
- Separate observed counts from hypotheses.
- A signal from one session cannot prove cross-session or concurrency safety.
- A hook firing does not prove that the desired user-visible outcome occurred.
- Model-lab and synthetic events are excluded and must not support runtime claims.
- Capability signals may name only IDs present in known_capabilities.
- Recommend the smallest deterministic runtime probe that could verify each
  material hypothesis.
- Keep the result concise and useful for a later human or primary-agent review.

INPUT_JSON:
""" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _valid_result(value: object, capability_ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "summary", "evidence_quality", "hook_findings", "capability_signals",
        "telemetry_gaps", "recommended_next_actions",
    }:
        return False
    quality = value.get("evidence_quality")
    if not isinstance(quality, dict) or set(quality) != {"rating", "reasons"}:
        return False
    if quality.get("rating") not in {"low", "medium", "high"}:
        return False
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        return False
    if not _string_list(quality.get("reasons"), 8):
        return False
    findings = value.get("hook_findings")
    signals = value.get("capability_signals")
    if not isinstance(findings, list) or len(findings) > 20:
        return False
    if not isinstance(signals, list) or len(signals) > 20:
        return False
    for item in findings:
        if (
            not isinstance(item, dict)
            or set(item) != {"hook", "severity", "finding", "evidence", "next_test"}
            or item.get("severity") not in {"info", "watch", "material"}
            or not all(
                isinstance(item.get(field), str) and item[field].strip()
                for field in ("hook", "finding", "next_test")
            )
            or not _string_list(item.get("evidence"), 6, minimum=1)
        ):
            return False
    for item in signals:
        if (
            not isinstance(item, dict)
            or set(item) != {"capability_id", "support", "reason"}
            or item.get("capability_id") not in capability_ids
            or item.get("support") not in {"none", "partial", "strong"}
            or not isinstance(item.get("reason"), str)
            or not item["reason"].strip()
        ):
            return False
    return (
        _string_list(value.get("telemetry_gaps"), 16)
        and _string_list(value.get("recommended_next_actions"), 12)
    )


def _string_list(value: object, maximum: int, minimum: int = 0) -> bool:
    return (
        isinstance(value, list)
        and minimum <= len(value) <= maximum
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _atomic_json(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _failure_kind(returncode: int, text: str) -> str:
    lowered = text.lower()
    if "quota" in lowered or "resource_exhausted" in lowered or "rate limit" in lowered:
        return "quota"
    if "auth" in lowered or "login" in lowered or "credential" in lowered or "ineligible" in lowered:
        return "authentication"
    if returncode == 124 or "timeout" in lowered or "deadline" in lowered:
        return "timeout"
    return "unavailable"


def _telemetry(root: pathlib.Path, status: str, elapsed: int = 0) -> None:
    scripts = root / "adapters" / "claude-code" / "plugin" / "hooks" / "scripts"
    try:
        sys.path.insert(0, str(scripts))
        import _hooklib
        _hooklib.log_event(
            "model_lab",
            {
                "provider": "google-antigravity", "model": os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL),
                "effort": EFFORT, "task": TASK, "status": status,
                "elapsed_bucket_s": min(600, max(0, int(elapsed // 10) * 10)),
            },
            {"_telemetry_origin": "model-lab"},
        )
    except Exception:
        pass


def _parse_wrapper(stdout: str) -> tuple[object, dict]:
    wrapper = json.loads(stdout)
    if not isinstance(wrapper, dict) or "structured_output" not in wrapper:
        raise ValueError("missing structured_output wrapper")
    meta = {
        key: wrapper[key]
        for key in ("conversation_id", "usage", "model") if key in wrapper
    }
    return wrapper["structured_output"], meta


def _cli_version(binary: str) -> str:
    try:
        proc = subprocess.run(
            [binary, "--version"], text=True, capture_output=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = proc.stdout.strip().splitlines()
    return value[0][:100] if proc.returncode == 0 and value else "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    root = _repo_root()
    telemetry_data = _load_tools(root)
    db = pathlib.Path(args.db).expanduser().resolve() if args.db else telemetry_data.default_db_path().resolve()
    payload = _source_payload(root, db)
    report = payload["telemetry"]
    if not report["active"] or report["error"] or report["usable_records"] == 0:
        return 0

    model = os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL)
    source_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    output_dir = _output_dir(root)
    destination = output_dir / f"telemetry-{source_digest[:16]}.json"
    pending = output_dir / f"pending-{source_digest[:16]}.json"
    if destination.exists() and not args.force:
        _telemetry(root, "deduplicated")
        return 0

    schema = root / "adapters" / "claude-code" / "dev" / "model-lab" / "schemas" / "telemetry-audit.json"
    binary = os.environ.get("MAINFRAME_ANTIGRAVITY_BIN", "agy")
    command = [
        binary,
        "--print", _prompt(payload), "--model", model, "--effort", EFFORT,
        "--mode", "plan", "--sandbox", "--disable-slash-commands",
        "--json-schema", str(schema), "--output-format", "json",
        "--print-timeout", "5m",
    ]
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        proc = subprocess.run(
            command, cwd=root, text=True, capture_output=True,
            timeout=TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        elapsed = int((datetime.datetime.now(datetime.timezone.utc) - started).total_seconds())
        _atomic_json(pending, {
            "schema": OUTPUT_SCHEMA, "status": "pending", "reason": "timeout" if isinstance(error, subprocess.TimeoutExpired) else "unavailable",
            "provider": "google-antigravity", "model": model, "effort": EFFORT,
            "source_sha256": source_digest, "last_attempt_at": started.isoformat(timespec="seconds"),
        })
        _telemetry(root, "unavailable", elapsed)
        return 0

    elapsed = int((datetime.datetime.now(datetime.timezone.utc) - started).total_seconds())
    if proc.returncode != 0:
        _atomic_json(pending, {
            "schema": OUTPUT_SCHEMA, "status": "pending",
            "reason": _failure_kind(proc.returncode, proc.stderr + "\n" + proc.stdout),
            "provider": "google-antigravity", "model": model, "effort": EFFORT,
            "source_sha256": source_digest, "last_attempt_at": started.isoformat(timespec="seconds"),
        })
        _telemetry(root, "unavailable", elapsed)
        return 0

    try:
        result, cli_meta = _parse_wrapper(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        _telemetry(root, "invalid", elapsed)
        return 0
    capability_ids = {item["id"] for item in payload["known_capabilities"] if item["id"]}
    if not _valid_result(result, capability_ids):
        _telemetry(root, "invalid", elapsed)
        return 0

    envelope = {
        "schema": OUTPUT_SCHEMA,
        "adapter": "claude-code",
        "producer": "gemini-telemetry-audit",
        "provider": "google-antigravity",
        "model": model,
        "effort": EFFORT,
        "task": TASK,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "sha256": source_digest,
            "database": db.name,
            "last_id": report["last_id"],
            "first_timestamp": report["first_timestamp"],
            "last_timestamp": report["last_timestamp"],
            "included_origins": report["included_origins"],
            "usable_records": report["usable_records"],
        },
        "cli": {"version": _cli_version(binary), **cli_meta},
        "review_required": True,
        "audit": result,
    }
    _atomic_json(destination, envelope)
    try:
        pending.unlink()
    except FileNotFoundError:
        pass
    _telemetry(root, "completed", elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
