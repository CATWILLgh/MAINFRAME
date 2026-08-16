#!/usr/bin/env python3
"""Run the frozen Gemini telemetry benchmark without changing runtime evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
WORKER_PATH = pathlib.Path(__file__).with_name("gemini-telemetry-audit.py")
CASES_PATH = (
    pathlib.Path(__file__).with_name("benchmarks") / "telemetry-audit-cases.json"
)
SCHEMA_PATH = pathlib.Path(__file__).with_name("schemas") / "telemetry-audit.json"


def _worker():
    spec = importlib.util.spec_from_file_location("gemini_telemetry_audit", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _payload(case: dict, capabilities: list[dict]) -> dict:
    return {
        "telemetry": case["input"]["telemetry"],
        "known_capabilities": capabilities,
        "limits": {
            "scope": "Frozen privacy-safe benchmark case; no external evidence.",
            "not_evidence": "Model conclusions remain candidates for deterministic review.",
            "evidence_quality_ceiling": case["expect"]["maximum_evidence_quality"],
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
            "benchmark_required_evidence_paths": case["expect"].get(
                "required_evidence_paths", []
            ),
            "benchmark_required_capability_support": case["expect"].get(
                "required_capability_support", {}
            ),
            "benchmark_required_probe_capabilities": case["expect"].get(
                "required_probe_capabilities", []
            ),
            "benchmark_required_probe_terms": case["expect"].get(
                "required_probe_terms", {}
            ),
            "benchmark_required_gap_ids": case["expect"].get("required_gap_ids", []),
        },
    }


def _capabilities() -> list[dict]:
    value = json.loads(
        (ROOT / ".agents/adapter-capabilities/catalog.json").read_text(encoding="utf-8")
    )
    return [
        {"id": row["id"], "outcome": row["outcome"]} for row in value["capabilities"]
    ]


def _run_case(binary: str, prompt: str, model: str, effort: str) -> tuple[object, dict]:
    command = [
        binary,
        "--print",
        prompt,
        "--model",
        model,
        "--effort",
        effort,
        "--mode",
        "plan",
        "--sandbox",
        "--disable-slash-commands",
        "--json-schema",
        str(SCHEMA_PATH),
        "--output-format",
        "json",
        "--print-timeout",
        "5m",
    ]
    import tempfile

    with tempfile.TemporaryDirectory(prefix="mainframe-gemini-benchmark-") as clean_cwd:
        process = subprocess.run(
            command,
            cwd=clean_cwd,
            text=True,
            capture_output=True,
            timeout=360,
            check=False,
        )
    if process.returncode != 0:
        return None, {"status": "unavailable", "returncode": process.returncode}
    try:
        result, meta = _worker()._parse_wrapper(process.stdout)
    except (json.JSONDecodeError, ValueError):
        return None, {"status": "invalid-wrapper"}
    return result, {"status": "completed", **meta}


def _legacy_grade(result: object, case: dict) -> dict:
    """Grade the old schema honestly; semantic expectations remain manual."""
    if not isinstance(result, dict):
        return {"passed": False, "reasons": ["No structured result."]}
    reasons = []
    # The legacy shape can mix observations and hypotheses inside the same
    # free-text finding. It therefore fails the agreed contract even when its
    # prose happens to be correct on one run.
    if "observations" not in result or "hypotheses" not in result:
        reasons.append("Observations and hypotheses are not structurally separated.")
    if "metric_interpretations" not in result:
        reasons.append(
            "The output cannot acknowledge hook counter semantics structurally."
        )
    reasons.append(
        "Required concepts and forbidden claims still need human semantic review in schema 1."
    )
    return {"passed": False, "reasons": reasons}


def _candidate_grade(
    result: object, case: dict, payload: dict, capabilities: list[dict]
) -> dict:
    reasons = []
    capability_ids = {row["id"] for row in capabilities}
    worker = _worker()
    if not worker._valid_result(result, capability_ids, payload):
        return {
            "passed": False,
            "reasons": ["Result failed schema or exact evidence-path validation."],
        }
    order = {"low": 0, "medium": 1, "high": 2}
    maximum = case["expect"]["maximum_evidence_quality"]
    if order[result["evidence_quality"]["rating"]] > order[maximum]:
        reasons.append(f"Evidence rating exceeds the case maximum {maximum}.")
    observed_paths = set()
    for observation in result["observations"]:
        observed_paths.update(evidence["path"] for evidence in observation["evidence"])
    missing_paths = (
        set(case["expect"].get("required_evidence_paths", [])) - observed_paths
    )
    if missing_paths:
        reasons.append(
            f"Required direct evidence paths were omitted: {sorted(missing_paths)}"
        )
    signal_support = {
        row["capability_id"]: row["support"] for row in result["capability_signals"]
    }
    for capability_id, expected_support in (
        case["expect"].get("required_capability_support", {}).items()
    ):
        if signal_support.get(capability_id) != expected_support:
            reasons.append(
                f"Capability {capability_id} must report support={expected_support}."
            )
    probe_capabilities = {probe["capability_id"] for probe in result["probes"]}
    missing_probe_capabilities = (
        set(case["expect"].get("required_probe_capabilities", [])) - probe_capabilities
    )
    if missing_probe_capabilities:
        reasons.append(
            f"Required deterministic probes were omitted: {sorted(missing_probe_capabilities)}"
        )
    probes_by_capability = {
        capability_id: " ".join(
            " ".join(
                (
                    probe["question"],
                    probe["method"],
                    probe["success_condition"],
                    probe["failure_condition"],
                )
            ).lower()
            for probe in result["probes"]
            if probe["capability_id"] == capability_id
        )
        for capability_id in probe_capabilities
    }
    for capability_id, terms in case["expect"].get("required_probe_terms", {}).items():
        probe_text = probes_by_capability.get(capability_id, "")
        missing_terms = [term for term in terms if term.lower() not in probe_text]
        if missing_terms:
            reasons.append(
                f"Probe for {capability_id} omits required method terms: {missing_terms}"
            )
    missing_gap_ids = set(case["expect"].get("required_gap_ids", [])) - set(
        result["gap_ids"]
    )
    if missing_gap_ids:
        reasons.append(
            f"Required telemetry gap IDs were omitted: {sorted(missing_gap_ids)}"
        )
    concurrency = [
        row
        for row in result["capability_signals"]
        if row["capability_id"] == "hooks.concurrent-session-safety"
    ]
    if concurrency and any(row["support"] != "none" for row in concurrency):
        reasons.append("Aggregate session counts cannot support concurrency safety.")
    if result["hypotheses"] and not result["probes"]:
        reasons.append("Hypotheses lack deterministic probes.")
    return {"passed": not reasons, "reasons": reasons}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("MAINFRAME_GEMINI_MODEL", "gemini-3.7-flash-high"),
    )
    parser.add_argument("--effort", default="high")
    parser.add_argument(
        "--binary", default=os.environ.get("MAINFRAME_ANTIGRAVITY_BIN", "agy")
    )
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args(argv)

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.case_ids:
        requested = set(args.case_ids)
        cases = [case for case in cases if case["id"] in requested]
        missing = requested - {case["id"] for case in cases}
        if missing:
            parser.error(f"unknown case ids: {', '.join(sorted(missing))}")
    capabilities = _capabilities()
    worker = _worker()
    report = {
        "schema": 2,
        "mode": "candidate",
        "model": args.model,
        "effort": args.effort,
        "cases": [],
    }
    for case in cases:
        case_capabilities = [
            row for row in capabilities if row["id"] in set(case["capability_ids"])
        ]
        payload = _payload(case, case_capabilities)
        result, meta = _run_case(
            args.binary,
            worker._prompt(payload),
            args.model,
            args.effort,
        )
        row = {
            "id": case["id"],
            "producer": meta,
            "grade": _candidate_grade(result, case, payload, case_capabilities),
            "result": result,
            "expect": case["expect"],
        }
        if args.summary_only:
            row.pop("result")
            row.pop("expect")
        report["cases"].append(row)
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 1 if any(not row["grade"]["passed"] for row in report["cases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
