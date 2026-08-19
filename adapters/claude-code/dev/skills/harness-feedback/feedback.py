#!/usr/bin/env python3
"""Claude Code entrypoint for the shared harness-feedback receiver."""

import importlib.util
import json
import pathlib
import os


def _receiver_path():
    source = pathlib.Path(__file__).resolve()
    candidates = [source, pathlib.Path.cwd()]
    state = pathlib.Path(os.path.expanduser(
        "~/.claude/.mainframe-managed-artifacts/dev-harness-feedback.json"
    ))
    try:
        candidates.append(pathlib.Path(json.loads(state.read_text())["source"]).resolve())
    except (OSError, ValueError, KeyError, TypeError):
        pass
    for candidate in candidates:
        for parent in (candidate, *candidate.parents):
            receiver = parent / "dev" / "harness-feedback" / "receiver.py"
            if receiver.is_file():
                return receiver
    raise RuntimeError("cannot locate the MAINFRAME harness-feedback receiver")


RECEIVER = _receiver_path()
SPEC = importlib.util.spec_from_file_location("mainframe_harness_feedback", RECEIVER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load harness-feedback receiver: {RECEIVER}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


if __name__ == "__main__":
    raise SystemExit(MODULE.main("claude-code"))
