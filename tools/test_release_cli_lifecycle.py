#!/usr/bin/env python3
"""Packaged CLI tests for exact local release activation and rollback."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_release


def test_packaged_cli_imports_switches_and_rolls_back_exact_releases():
    sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
    try:
        first = sandbox / "release-a"
        second = sandbox / "release-b"
        build_release.build(REPO, first, release_id="release-a")
        build_release.build(REPO, second, release_id="release-b")
        home = sandbox / "home"
        home.mkdir()
        environment = _environment(home)
        binary = first / "bin/mainframe"

        first_review = _review_local(binary, first, environment)
        assert first_review["operations"][0]["kind"] == "install"
        _assert_review_read_only(home)
        _apply(binary, first_review, environment)
        _assert_active(home, first_review["target"])

        second_review = _review_local(binary, second, environment)
        assert second_review["previous"] == first_review["target"]
        assert second_review["operations"][0]["kind"] == "replace"
        _apply(binary, second_review, environment)
        _assert_active(home, second_review["target"])

        rollback = _review_cached(binary, first_review["target"], environment)
        assert rollback["previous"] == second_review["target"]
        _apply(binary, rollback, environment)
        _assert_active(home, first_review["target"])

        no_change = _review_cached(binary, first_review["target"], environment)
        assert no_change["applicable"] is False
        assert "apply_request" not in no_change
        _assert_no_adapter_roots(home)
    finally:
        _make_tree_removable(sandbox)
        shutil.rmtree(sandbox)


def _environment(home: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("MAINFRAME_RELEASE_ROOT", None)
    environment.update(
        HOME=str(home),
        CODEX_HOME=str(home / ".codex"),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local/share"),
        XDG_STATE_HOME=str(home / ".local/state"),
    )
    return environment


def _review_local(
    binary: Path,
    source: Path,
    environment: dict[str, str],
) -> dict:
    return _run_json(
        binary,
        ["release", "review"],
        {
            "schema_version": 1,
            "kind": "mainframe-release-change",
            "operation": "import-and-activate",
            "source_path": str(source),
        },
        environment,
    )


def _review_cached(
    binary: Path,
    identity: dict,
    environment: dict[str, str],
) -> dict:
    return _run_json(
        binary,
        ["release", "review"],
        {
            "schema_version": 1,
            "kind": "mainframe-release-change",
            "operation": "activate-cached",
            "release_id": identity["id"],
            "index_sha256": identity["index_sha256"],
        },
        environment,
    )


def _apply(
    binary: Path,
    review: dict,
    environment: dict[str, str],
) -> dict:
    return _run_json(
        binary,
        ["release", "apply", "--confirm", review["expected_review"]],
        review["apply_request"],
        environment,
    )


def _run_json(
    binary: Path,
    arguments: list[str],
    request: dict,
    environment: dict[str, str],
) -> dict:
    result = subprocess.run(
        [str(binary), *arguments],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        env=environment,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _assert_review_read_only(home: Path) -> None:
    for relative in (
        ".local/share/mainframe",
        ".local/bin",
        ".local/state/mainframe",
    ):
        assert not (home / relative).exists()


def _assert_active(home: Path, identity: dict) -> None:
    launcher = home / ".local/bin/mainframe"
    expected = (
        home
        / ".local/share/mainframe/releases"
        / identity["id"]
        / identity["index_sha256"]
        / "bin/mainframe"
    )
    assert launcher.is_symlink()
    assert Path(os.readlink(launcher)) == expected


def _assert_no_adapter_roots(home: Path) -> None:
    for relative in (".claude", ".codex", ".config/opencode", ".gemini"):
        assert not (home / relative).exists()


def _make_tree_removable(root: Path) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        if path.is_dir():
            path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700)


if __name__ == "__main__":
    test_packaged_cli_imports_switches_and_rolls_back_exact_releases()
