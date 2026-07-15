#!/usr/bin/env python3
"""Isolated filesystem contract tests for legacy symlink cleanup."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
SYSTEM_PATH = "/usr/bin:/bin"
FIXED_TIMESTAMP = "20260715-120000"
LEGACY_PATHS = (
    "skills/code-audit",
    "agents/web-search.md",
    "hooks/bash-pattern-reminder.py",
    "hooks/rules",
)
TOOL_BINARIES = (
    "ruff",
    "pip-audit",
    "semgrep",
    "osv-scanner",
    "oxlint",
    "depcruise",
    "knip",
    "fallow",
)


def _write(path: Path, text: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> None:
    _write(path, text)
    path.chmod(0o755)


def _seed_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    shutil.copy2(INSTALLER, repo / "install.sh")
    for relative in (
        "dist/claude-code/CLAUDE.md",
        "dist/claude-code/settings.json",
        "dist/claude-code/plugin/manifest.json",
        "dist/claude-code/output-styles/default.md",
        "dist/claude-code/scripts/secret",
        "dist/claude-code/templates/credentials-index.md",
    ):
        _write(repo / relative)
    return repo


@dataclass(frozen=True)
class Fixture:
    root: Path
    repo: Path
    home: Path
    env: dict[str, str]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(self.repo / "install.sh"), *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )


@contextmanager
def _fixture() -> Iterator[Fixture]:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        repo = _seed_repo(root)
        home = root / "home"
        fake_bin = root / "bin"
        fake_bin.mkdir()
        for binary in TOOL_BINARIES:
            _write_executable(fake_bin / binary)
        _write_executable(
            fake_bin / "date",
            f"#!/bin/sh\nprintf '%s\\n' '{FIXED_TIMESTAMP}'\n",
        )
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "CODEX_HOME": str(root / "codex"),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        }
        yield Fixture(root, repo, home, env)


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def _seed_foreign_links(fixture: Fixture, *, live: bool) -> dict[Path, str]:
    links = {}
    for relative in LEGACY_PATHS:
        target = fixture.root / "foreign" / relative
        if live:
            _write(target)
        link = fixture.home / ".claude" / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        links[link] = os.readlink(link)
    return links


def _assert_links_unchanged(links: dict[Path, str]) -> None:
    for link, target in links.items():
        assert link.is_symlink(), f"link was removed: {link}"
        assert os.readlink(link) == target


def test_foreign_live_and_broken_links_survive_lifecycle() -> None:
    for live in (True, False):
        with _fixture() as fixture:
            links = _seed_foreign_links(fixture, live=live)
            _assert_success(fixture.run())
            _assert_links_unchanged(links)
            _assert_success(fixture.run())
            _assert_links_unchanged(links)
            _assert_success(fixture.run("--uninstall"))
            _assert_links_unchanged(links)


def test_relative_and_moved_checkout_links_are_preserved() -> None:
    with _fixture() as fixture:
        relative_link = fixture.home / ".claude/skills/code-audit"
        relative_link.parent.mkdir(parents=True)
        relative_link.symlink_to("../../../repo/export/skills/code-audit")
        moved_link = fixture.home / ".claude/agents/web-search.md"
        moved_link.parent.mkdir(parents=True)
        moved_link.symlink_to(fixture.root / "old-repo/export/agents/web-search.md")
        links = {
            relative_link: os.readlink(relative_link),
            moved_link: os.readlink(moved_link),
        }
        _assert_success(fixture.run())
        _assert_links_unchanged(links)


def _seed_owned_links(fixture: Fixture) -> dict[Path, str]:
    links = {}
    for index, relative in enumerate(LEGACY_PATHS):
        target = fixture.repo / "export" / relative
        if index % 2 == 0:
            _write(target)
        link = fixture.home / ".claude" / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        links[link] = os.readlink(link)
    return links


def test_verified_legacy_links_are_backed_up_once() -> None:
    with _fixture() as fixture:
        links = _seed_owned_links(fixture)
        _assert_success(fixture.run())
        backup_root = fixture.home / f".claude/.backup-{FIXED_TIMESTAMP}"
        for link, target in links.items():
            assert not link.is_symlink()
            backup = backup_root / link.relative_to(fixture.home / ".claude")
            assert backup.is_symlink(), f"backup missing: {backup}"
            assert os.readlink(backup) == target
        backups = sorted(fixture.home.glob(".claude/.backup-*"))
        _assert_success(fixture.run())
        assert sorted(fixture.home.glob(".claude/.backup-*")) == backups


def test_dry_run_reports_backup_without_mutation() -> None:
    with _fixture() as fixture:
        links = _seed_owned_links(fixture)
        result = fixture.run("--dry-run")
        _assert_success(result)
        _assert_links_unchanged(links)
        assert not list(fixture.home.glob(".claude/.backup-*"))
        assert "would back up 4 verified pre-migration symlinks" in result.stdout


def test_empty_user_layer_directories_survive() -> None:
    with _fixture() as fixture:
        agents = fixture.home / ".claude/agents"
        hooks = fixture.home / ".claude/hooks"
        agents.mkdir(parents=True)
        hooks.mkdir()
        _assert_success(fixture.run())
        assert agents.is_dir()
        assert hooks.is_dir()


def test_backup_failure_stops_install_without_success_claim() -> None:
    with _fixture() as fixture:
        links = _seed_owned_links(fixture)
        conflict = fixture.home / f".claude/.backup-{FIXED_TIMESTAMP}"
        _write(conflict)
        result = fixture.run()
        output = result.stdout + result.stderr
        assert result.returncode != 0, output
        assert "Install complete" not in output
        assert "moved " not in output
        for link in links:
            assert link.is_symlink(), f"failed backup removed {link}"


def main() -> int:
    tests = [value for key, value in sorted(globals().items())
             if key.startswith("test_") and callable(value)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"  FAIL {test.__name__}: {error}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
