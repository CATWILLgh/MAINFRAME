#!/usr/bin/env python3
"""Integration contract for the legacy DEV diagnostics bootstrap."""

from __future__ import annotations

import json
import stat
import subprocess
import tempfile
from pathlib import Path

from test_install import SYSTEM_PATH, _seed_repo, _write, _write_executable


def _dev_fixture(root: Path) -> tuple[Path, Path, dict[str, str]]:
    installer = _seed_repo(root)
    repo = installer.parent
    fake_bin = root / "bin"
    fake_bin.mkdir()
    for program in ("ruff", "pip-audit", "semgrep", "osv-scanner",
                    "oxlint", "depcruise", "knip", "fallow"):
        _write_executable(fake_bin / program)
    _write(
        repo / "dev/harness-feedback-plugin/.claude-plugin/plugin.json",
        '{"name":"mainframe-dev","version":"0.1.0"}\n',
    )
    _write(
        repo / "dev/harness-feedback-plugin/skills/harness-feedback/SKILL.md"
    )
    env = {"HOME": str(root / "home"), "PATH": f"{fake_bin}:{SYSTEM_PATH}"}
    return installer, repo, env


def _run_dev(installer: Path, repo: Path, env: dict[str, str]):
    return subprocess.run(
        ["/bin/bash", str(installer), "--dev"], cwd=repo, env=env,
        capture_output=True, text=True, timeout=30, check=False)


def test_dev_runtime_bootstrap_content_modes_and_preservation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        installer, repo, env = _dev_fixture(Path(temp).resolve())
        runtime = repo / "workspace/runtime"
        _write(runtime / "feedback/existing.md", "preserve\n")
        result = _run_dev(installer, repo, env)
        assert result.returncode == 0, result.stdout + result.stderr
        config = runtime / "diagnostics.json"
        assert json.loads(config.read_text()) == {
            "schema_version": 1, "events": True, "feedback": True}
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        for name in ("telemetry", "feedback"):
            assert stat.S_IMODE((runtime / name).stat().st_mode) == 0o700
        assert (runtime / "feedback/existing.md").read_text() == "preserve\n"


def test_dev_runtime_refuses_a_diagnostics_symlink() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer, repo, env = _dev_fixture(root)
        runtime = repo / "workspace/runtime"
        runtime.mkdir(parents=True)
        target = root / "must-remain-unchanged"
        target.write_text("preserve\n")
        (runtime / "diagnostics.json").symlink_to(target)
        result = _run_dev(installer, repo, env)
        assert result.returncode != 0, result.stdout + result.stderr
        assert target.read_text() == "preserve\n"
        assert not (root / "home").exists()
        assert not (runtime / "telemetry").exists()
        assert not (runtime / "feedback").exists()


def test_dev_install_migrates_only_the_repo_owned_legacy_feedback_link() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer, repo, env = _dev_fixture(root)
        legacy = root / "home/.claude/skills/harness-feedback"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(repo / "dev/skills/harness-feedback")

        result = _run_dev(installer, repo, env)

        assert result.returncode == 0, result.stdout + result.stderr
        assert not legacy.exists() and not legacy.is_symlink()
        installed = root / "home/.claude/skills/mainframe-dev"
        assert installed.resolve() == (
            repo / "dev/harness-feedback-plugin"
        ).resolve()


def test_dev_install_preserves_a_foreign_legacy_feedback_link() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer, repo, env = _dev_fixture(root)
        foreign = root / "foreign-feedback"
        foreign.mkdir()
        legacy = root / "home/.claude/skills/harness-feedback"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(foreign)

        result = _run_dev(installer, repo, env)

        assert result.returncode == 0, result.stdout + result.stderr
        assert legacy.resolve() == foreign


def test_uninstall_removes_only_the_repo_owned_legacy_feedback_link() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer, repo, env = _dev_fixture(root)
        legacy = root / "home/.claude/skills/harness-feedback"
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(repo / "dev/skills/harness-feedback")

        result = subprocess.run(
            ["/bin/bash", str(installer), "--uninstall"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert not legacy.exists() and not legacy.is_symlink()


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
    print(f"{len(tests)}/{len(tests)} passed")
