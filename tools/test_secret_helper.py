#!/usr/bin/env python3
"""Behavior tests for the shared ``secret`` helper."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SECRET = ROOT / "shared" / "credentials" / "secret"


def _env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "ORDINARY_SETTING": "kept",
    })
    return env


def _run(root: Path, *args: str, env: dict[str, str] | None = None):
    return subprocess.run(
        [str(SECRET), *args],
        capture_output=True,
        text=True,
        env=env or _env(root),
        timeout=10,
    )


def _seed(root: Path) -> dict[str, str]:
    env = _env(root)
    for name, value in (
        ("SELECTED_TOKEN", "synthetic selected value"),
        ("SECOND_TOKEN", "synthetic second value"),
        ("UNSELECTED_TOKEN", "synthetic unselected value"),
    ):
        result = _run(root, "set", name, value, env=env)
        assert result.returncode == 0, result.stderr
        env[name] = value
    return env


def test_run_exposes_only_selected_store_names_to_one_child():
    root = Path(tempfile.mkdtemp(prefix="mainframe-secret-test-"))
    env = _seed(root)
    code = (
        "import os; "
        "assert os.environ['SELECTED_TOKEN'] == 'synthetic selected value'; "
        "assert os.environ['SECOND_TOKEN'] == 'synthetic second value'; "
        "assert 'UNSELECTED_TOKEN' not in os.environ; "
        "assert os.environ['ORDINARY_SETTING'] == 'kept'"
    )
    result = _run(
        root, "run", "SELECTED_TOKEN", "SECOND_TOKEN", "--",
        sys.executable, "-c", code,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_run_requires_names_separator_command_and_existing_values():
    root = Path(tempfile.mkdtemp(prefix="mainframe-secret-test-"))
    env = _seed(root)
    for args in (
        ("run",),
        ("run", "SELECTED_TOKEN"),
        ("run", "SELECTED_TOKEN", "--"),
    ):
        result = _run(root, *args, env=env)
        assert result.returncode == 2, args
        assert result.stdout == ""

    marker = root / "must-not-exist"
    result = _run(
        root,
        "run", "MISSING_TOKEN", "--", sys.executable, "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch()",
        env=env,
    )
    assert result.returncode == 1
    assert not marker.exists()


def test_run_returns_the_child_status_without_printing_values():
    root = Path(tempfile.mkdtemp(prefix="mainframe-secret-test-"))
    env = _seed(root)
    result = _run(
        root, "run", "SELECTED_TOKEN", "--", sys.executable, "-c",
        "raise SystemExit(23)", env=env,
    )
    assert result.returncode == 23
    assert "synthetic selected value" not in result.stdout + result.stderr


if __name__ == "__main__":
    failures = 0
    for name, value in sorted(globals().items()):
        if not name.startswith("test_") or not callable(value):
            continue
        try:
            value()
            print(f"  ok  {name}")
        except Exception as error:
            failures += 1
            print(f"FAIL  {name}: {error}")
    raise SystemExit(1 if failures else 0)
