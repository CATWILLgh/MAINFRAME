#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import BinaryIO, TextIO


ADAPTER_DIR = Path(__file__).resolve().parents[1]
GATES_DIR = Path(__file__).resolve().parent

def _load_local_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_hook_config_path() -> Path:
    # Installed runtime ships hook_config.py alongside this module under gates/
    # (the zcode-desktop.gates install unit symlinks the whole tree). Source
    # layout keeps it at the adapter root for build_bundle.py to import; tests
    # load this module from source, so ADAPTER_DIR is the fallback there.
    candidates = (GATES_DIR / "hook_config.py", ADAPTER_DIR / "hook_config.py")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"hook_config.py not found in any of: {[str(p) for p in candidates]}"
    )


hook_config = _load_local_module(
    "zcode_mainframe_hook_config", _resolve_hook_config_path()
)
runtime = _load_local_module(
    "zcode_mainframe_hook_runtime", GATES_DIR / "mainframe_runtime.py"
)
CORE_EVENT_DETECTORS = hook_config.CORE_EVENT_DETECTORS
SUPPORTED_EVENTS = hook_config.SUPPORTED_EVENTS
BridgeInputError = runtime.BridgeInputError
normalize_payload = runtime.normalize_payload
run_detectors = runtime.run_detectors


MAX_INPUT_BYTES = 1_048_576
MAX_DETECTOR_OUTPUT_BYTES = 65_536
DETECTOR_TIMEOUT_SECONDS = 8.0


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BridgeInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_payload(stdin: BinaryIO) -> dict[str, object]:
    raw = stdin.read(MAX_INPUT_BYTES + 1)
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > MAX_INPUT_BYTES:
        raise BridgeInputError("hook input exceeded the limit")
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeInputError("hook input is not valid JSON") from exc
    if not isinstance(value, dict):
        raise BridgeInputError("hook input must be a JSON object")
    return value


def _degradation_output(event: str, message: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": f"MAINFRAME hook bridge degraded: {message}",
        }
    }


def _write_json(stdout: TextIO, output: dict[str, object] | None) -> None:
    if output is not None:
        stdout.write(json.dumps(output, ensure_ascii=False) + "\n")


def run(
    argv: list[str],
    *,
    stdin: BinaryIO = sys.stdin.buffer,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    if len(argv) != 1 or argv[0] not in SUPPORTED_EVENTS:
        stderr.write("MAINFRAME ZCode hook bridge: unsupported event argument\n")
        return 0
    event = argv[0]
    try:
        payload = normalize_payload(event, _read_payload(stdin))
    except BridgeInputError as exc:
        stderr.write(f"MAINFRAME ZCode hook bridge degraded: {exc}\n")
        _write_json(stdout, _degradation_output(event, str(exc)))
        return 0
    detector_dir = Path(
        os.environ.get("MAINFRAME_ZCODE_DETECTORS_DIR", GATES_DIR / "detectors")
    )
    detectors = CORE_EVENT_DETECTORS.get(event, ())
    result = run_detectors(
        event,
        payload,
        detectors,
        detector_dir,
        timeout_seconds=DETECTOR_TIMEOUT_SECONDS,
        max_output_bytes=MAX_DETECTOR_OUTPUT_BYTES,
    )
    for diagnostic in result.diagnostics:
        stderr.write(f"MAINFRAME ZCode hook bridge degraded: {diagnostic}\n")
    if result.exit_code == 2:
        stderr.write((result.block_reason or "MAINFRAME detector blocked the event") + "\n")
        return 2
    _write_json(stdout, result.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
