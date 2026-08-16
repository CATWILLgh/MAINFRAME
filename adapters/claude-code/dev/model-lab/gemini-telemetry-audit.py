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
OUTPUT_SCHEMA = 2
TIMEOUT_SECONDS = 360
RUNTIME_ORIGINS = {"runtime", "runtime-inferred"}
LIMITATION_IDS = {
    "aggregate-only",
    "mixed-runtime-provenance",
    "event-order-unavailable",
    "surface-unattributed",
    "session-overlap-unknown",
    "cross-session-unproven",
    "hook-invocation-count-unavailable",
    "finding-denominator-unavailable",
    "user-visible-outcome-unproven",
}


def _repo_root() -> pathlib.Path:
    override = os.environ.get("MAINFRAME_PROJECT_ROOT")
    return (
        pathlib.Path(override).resolve()
        if override
        else pathlib.Path(__file__).resolve().parents[4]
    )


def _output_dir(root: pathlib.Path) -> pathlib.Path:
    override = os.environ.get("MAINFRAME_MODEL_LAB_ROOT")
    base = (
        pathlib.Path(override).resolve()
        if override
        else root / "workspace" / "runtime" / "claude-code" / "model-lab"
    )
    return base / "gemini" / "telemetry-audits"


def _load_tools(root: pathlib.Path):
    tools = root / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import telemetry_data

    return telemetry_data


def _read_capabilities(root: pathlib.Path) -> list[dict]:
    override = os.environ.get("MAINFRAME_CAPABILITY_CATALOG")
    path = (
        pathlib.Path(override).resolve()
        if override
        else root / ".agents" / "adapter-capabilities" / "catalog.json"
    )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for item in value.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": item.get("id", ""),
                "outcome": item.get("outcome", ""),
            }
        )
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
            "active",
            "format_version",
            "usable_records",
            "sessions",
            "agent_instances",
            "first_timestamp",
            "last_timestamp",
            "last_id",
            "included_origins",
            "event_counts",
            "by_day",
            "by_agent",
            "agent_lifecycle",
            "breakdowns",
            "hook_effectiveness",
            "error",
        )
    }
    return {
        "telemetry": telemetry,
        "known_capabilities": _read_capabilities(root),
        "limits": {
            "scope": "Aggregate, privacy-safe Claude Code adapter telemetry only.",
            "not_evidence": "Model conclusions are candidates for independent verification, not capability proof.",
            "historical_origin": "runtime-inferred means a legacy row matched the Claude UUID session shape; it was not rewritten.",
            "evidence_quality_ceiling": "medium",
            "hook_metric_semantics": {
                "signals": "Number of telemetry rows for this hook and rule.",
                "sessions": "Distinct sessions represented by those rows.",
                "noted": "Sum of noted finding counts, not hook calls or retries.",
                "asked": "Sum of asked finding counts, not hook calls or retries.",
                "blocked": "Sum of blocked finding counts, not hook calls or retries.",
                "resolved": "Sum of resolved finding counts, not hook calls or retries.",
                "context_chars": "Sum of model-visible context characters recorded by the rows.",
            },
            "session_boundary": "A distinct-session count does not reveal temporal overlap or prove concurrency safety.",
        },
    }


def _prompt(payload: dict) -> str:
    return """You are auditing MAINFRAME's Claude Code adapter telemetry.

Analyze only the JSON supplied below. Do not browse, inspect other files, run
commands, or infer behavior absent from the aggregates. Return exactly the
supplied JSON schema.

Rules:
- Return concise English in hypotheses and probes.
- Observations contain only exact input pointers and values. Put every interpretation,
  suspected cause, risk, missing-ingestion claim, retry claim, effectiveness
  claim, ratio, or causal statement in hypotheses.
- Every observation must cite one or more JSON Pointer paths into INPUT_JSON.
  Copy each cited primitive value exactly into evidence.value.
- `signals` is the number of telemetry rows. `noted`, `asked`, `blocked`, and
  `resolved` are summed finding counts; they are not calls, retries, turns, or
  denominators for an effectiveness rate.
- A distinct-session count does not reveal temporal overlap.
- Copy the five supplied measurement boundaries exactly into
  measurement_boundaries; they are deterministic input semantics, not model
  conclusions.
- Do not rate evidence above limits.evidence_quality_ceiling when that field is
  supplied.
- A signal from one session cannot prove cross-session or concurrency safety.
- A hook firing does not prove that the desired user-visible outcome occurred.
- Model-lab and synthetic events are excluded and must not support runtime claims.
- Capability signals may name only IDs present in known_capabilities.
- Every hypothesis must reference observations and a smallest deterministic
  probe. If no bounded probe exists, omit the hypothesis.
- When limits contains benchmark_required_* fields, satisfy those exact
  evidence, capability-support, and probe-ownership requirements.
- Select only the supplied standardized limitation and gap IDs. Do not create
  prose summaries or prose evidence claims; MAINFRAME renders its own summary.

INPUT_JSON:
""" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _pointer(payload: object, path: str) -> object:
    if not isinstance(path, str) or not path.startswith("/"):
        raise KeyError(path)
    value = payload
    for raw in path[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise KeyError(path)
    return value


def _valid_result(value: object, capability_ids: set[str], payload: dict) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "evidence_quality",
        "observations",
        "hypotheses",
        "measurement_boundaries",
        "capability_signals",
        "gap_ids",
        "probes",
    }:
        return False
    if value.get("measurement_boundaries") != {
        "finding_counts": "finding-sums-not-invocations",
        "retry_behavior": "unknown",
        "session_overlap": "unknown",
        "cross_session_safety": "unproven",
        "causal_effectiveness": "unproven",
    }:
        return False
    quality = value.get("evidence_quality")
    if not isinstance(quality, dict) or set(quality) != {"rating", "limitation_ids"}:
        return False
    if quality.get("rating") not in {"low", "medium", "high"}:
        return False
    ceiling = payload.get("limits", {}).get("evidence_quality_ceiling")
    quality_order = {"low": 0, "medium": 1, "high": 2}
    if (
        ceiling in quality_order
        and quality_order[quality["rating"]] > quality_order[ceiling]
    ):
        return False
    if not _known_ids(quality.get("limitation_ids"), LIMITATION_IDS, 8):
        return False
    observations = value.get("observations")
    hypotheses = value.get("hypotheses")
    signals = value.get("capability_signals")
    probes = value.get("probes")
    if not isinstance(observations, list) or not observations or len(observations) > 24:
        return False
    if not isinstance(hypotheses, list) or len(hypotheses) > 16:
        return False
    if not isinstance(signals, list) or len(signals) > 20:
        return False
    if not isinstance(probes, list) or len(probes) > 16:
        return False
    observation_ids: set[str] = set()
    for item in observations:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "evidence"}
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
            or item["id"] in observation_ids
            or not isinstance(item.get("evidence"), list)
            or not item["evidence"]
            or len(item["evidence"]) > 8
        ):
            return False
        observation_ids.add(item["id"])
        for evidence in item["evidence"]:
            if not isinstance(evidence, dict) or set(evidence) != {"path", "value"}:
                return False
            try:
                expected = _pointer(payload, evidence["path"])
            except (KeyError, IndexError, ValueError, TypeError):
                return False
            if isinstance(expected, (dict, list)) or evidence["value"] != expected:
                return False

    probe_ids: set[str] = set()
    for item in probes:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "id",
                "capability_id",
                "question",
                "method",
                "success_condition",
                "failure_condition",
            }
            or not all(
                isinstance(item.get(field), str) and item[field].strip()
                for field in item
            )
            or item.get("capability_id") not in capability_ids
            or item["id"] in probe_ids
        ):
            return False
        probe_ids.add(item["id"])

    hypothesis_ids: set[str] = set()
    for item in hypotheses:
        if (
            not isinstance(item, dict)
            or set(item)
            != {"id", "statement", "observation_ids", "confidence", "probe_id"}
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
            or item["id"] in hypothesis_ids
            or not isinstance(item.get("statement"), str)
            or not item["statement"].strip()
            or item.get("confidence") not in {"low", "medium"}
            or not _string_list(item.get("observation_ids"), 8, minimum=1)
            or not set(item["observation_ids"]).issubset(observation_ids)
            or item.get("probe_id") not in probe_ids
        ):
            return False
        hypothesis_ids.add(item["id"])
    for item in signals:
        if (
            not isinstance(item, dict)
            or set(item) != {"capability_id", "support", "observation_ids"}
            or item.get("capability_id") not in capability_ids
            or item.get("support") not in {"none", "partial", "strong"}
            or not _string_list(item.get("observation_ids"), 8, minimum=1)
            or not set(item["observation_ids"]).issubset(observation_ids)
        ):
            return False
    return _known_ids(value.get("gap_ids"), LIMITATION_IDS, 16, minimum=1)


def _string_list(value: object, maximum: int, minimum: int = 0) -> bool:
    return (
        isinstance(value, list)
        and minimum <= len(value) <= maximum
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _known_ids(
    value: object, allowed: set[str], maximum: int, minimum: int = 0
) -> bool:
    return _string_list(value, maximum, minimum) and set(value).issubset(allowed)


def _canonical_summary(payload: dict) -> str:
    telemetry = payload["telemetry"]
    return (
        f"Analyzed {telemetry.get('usable_records', 0)} aggregate telemetry rows "
        f"across {telemetry.get('sessions', 0)} sessions. Finding counters are "
        "sums, not invocation counts; retry behavior and temporal overlap are "
        "unknown; cross-session safety and causal effectiveness remain unproven."
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
    if (
        "auth" in lowered
        or "login" in lowered
        or "credential" in lowered
        or "ineligible" in lowered
    ):
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
                "provider": "google-antigravity",
                "model": os.environ.get("MAINFRAME_GEMINI_MODEL", MODEL),
                "effort": EFFORT,
                "task": TASK,
                "status": status,
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
        for key in ("conversation_id", "usage", "model")
        if key in wrapper
    }
    return wrapper["structured_output"], meta


def _cli_version(binary: str) -> str:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
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
    db = (
        pathlib.Path(args.db).expanduser().resolve()
        if args.db
        else telemetry_data.default_db_path().resolve()
    )
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

    schema = (
        root
        / "adapters"
        / "claude-code"
        / "dev"
        / "model-lab"
        / "schemas"
        / "telemetry-audit.json"
    )
    binary = os.environ.get("MAINFRAME_ANTIGRAVITY_BIN", "agy")
    command = [
        binary,
        "--print",
        _prompt(payload),
        "--model",
        model,
        "--effort",
        EFFORT,
        "--mode",
        "plan",
        "--sandbox",
        "--disable-slash-commands",
        "--json-schema",
        str(schema),
        "--output-format",
        "json",
        "--print-timeout",
        "5m",
    ]
    started = datetime.datetime.now(datetime.timezone.utc)
    try:
        with tempfile.TemporaryDirectory(prefix="mainframe-gemini-audit-") as clean_cwd:
            proc = subprocess.run(
                command,
                cwd=clean_cwd,
                text=True,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        elapsed = int(
            (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
        )
        _atomic_json(
            pending,
            {
                "schema": OUTPUT_SCHEMA,
                "status": "pending",
                "reason": "timeout"
                if isinstance(error, subprocess.TimeoutExpired)
                else "unavailable",
                "provider": "google-antigravity",
                "model": model,
                "effort": EFFORT,
                "source_sha256": source_digest,
                "last_attempt_at": started.isoformat(timespec="seconds"),
            },
        )
        _telemetry(root, "unavailable", elapsed)
        return 0

    elapsed = int(
        (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()
    )
    if proc.returncode != 0:
        _atomic_json(
            pending,
            {
                "schema": OUTPUT_SCHEMA,
                "status": "pending",
                "reason": _failure_kind(
                    proc.returncode, proc.stderr + "\n" + proc.stdout
                ),
                "provider": "google-antigravity",
                "model": model,
                "effort": EFFORT,
                "source_sha256": source_digest,
                "last_attempt_at": started.isoformat(timespec="seconds"),
            },
        )
        _telemetry(root, "unavailable", elapsed)
        return 0

    try:
        result, cli_meta = _parse_wrapper(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        _telemetry(root, "invalid", elapsed)
        return 0
    capability_ids = {
        item["id"] for item in payload["known_capabilities"] if item["id"]
    }
    if not _valid_result(result, capability_ids, payload):
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
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
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
        "summary": _canonical_summary(payload),
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
