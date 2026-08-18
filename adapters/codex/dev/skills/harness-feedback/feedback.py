#!/usr/bin/env python3
"""Codex entrypoint for the shared harness-feedback receiver."""

import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[5]
RECEIVER = ROOT / "dev" / "harness-feedback" / "receiver.py"
SPEC = importlib.util.spec_from_file_location("mainframe_harness_feedback", RECEIVER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load harness-feedback receiver: {RECEIVER}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


if __name__ == "__main__":
    raise SystemExit(MODULE.main("codex"))
