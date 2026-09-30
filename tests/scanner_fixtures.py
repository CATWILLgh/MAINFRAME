"""Hermetic security-scanner executables for native adapter tests."""

from __future__ import annotations

import os
from pathlib import Path


def scanner_path(root: Path) -> str:
    """Return PATH with deterministic Ruff and Oxlint stand-ins first."""
    directory = root / "scanner-bin"
    directory.mkdir()
    ruff = directory / "ruff"
    ruff.write_text(
        """#!/usr/bin/env python3
import json
import sys

source = sys.stdin.read()
findings = []
if "shell=True" in source:
    findings.append({
        "code": "S602",
        "message": "subprocess call with shell=True",
        "location": {"row": 3},
        "end_location": {"row": 3},
    })
print(json.dumps(findings))
raise SystemExit(1 if findings else 0)
""",
        encoding="utf-8",
    )
    oxlint = directory / "oxlint"
    oxlint.write_text(
        """#!/usr/bin/env python3
print('{"diagnostics":[]}')
""",
        encoding="utf-8",
    )
    ruff.chmod(0o755)
    oxlint.chmod(0o755)
    return str(directory) + os.pathsep + os.environ.get("PATH", "")
