#!/usr/bin/env python3
"""Real-filesystem lifecycle tests for the Antigravity desktop plugin link."""

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
TOOL_BINARIES = (
    "ruff", "pip-audit", "semgrep", "osv-scanner", "oxlint",
    "depcruise", "knip", "fallow",
)


def _write(path: Path, text: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> None:
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
        "dist/antigravity-2/plugin/plugin.json",
        "core/resources/credentials-index.md",
    ):
        _write(repo / relative)
    _executable(repo / ".venv/bin/python3")
    return repo


@dataclass(frozen=True)
class Fixture:
    root: Path
    repo: Path
    home: Path
    env: dict[str, str]

    @property
    def plugin(self) -> Path:
        return self.home / ".gemini/config/plugins/mainframe"

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
            _executable(fake_bin / binary)
        _executable(fake_bin / "date", f"#!/bin/sh\nprintf '%s\\n' '{FIXED_TIMESTAMP}'\n")
        app = root / "Antigravity.app/Contents"
        app.mkdir(parents=True)
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "CODEX_HOME": str(root / "codex"),
            "ANTIGRAVITY_APP": str(root / "Antigravity.app"),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        }
        yield Fixture(root, repo, home, env)


def _success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_backup_link_idempotency_and_owned_uninstall() -> None:
    with _fixture() as fixture:
        _write(fixture.plugin / "user-plugin.json", "user data\n")
        memory = fixture.home / ".gemini/antigravity/mainframe-memory/keep.md"
        _write(memory, "durable\n")

        _success(fixture.run("--antigravity-2"))
        expected = fixture.repo / "dist/antigravity-2/plugin"
        assert fixture.plugin.is_symlink()
        assert Path(os.readlink(fixture.plugin)) == expected
        backup = (
            fixture.home / f".gemini/config/.mainframe-backup-{FIXED_TIMESTAMP}"
            "/plugins/mainframe/user-plugin.json"
        )
        assert backup.read_text() == "user data\n"
        index = fixture.home / ".gemini/antigravity/credentials-index.md"
        assert index.read_text() == "fixture\n"
        assert index.stat().st_mode & 0o777 == 0o600

        _success(fixture.run("--antigravity-2"))
        assert fixture.plugin.is_symlink()
        assert len(list((fixture.home / ".gemini/config").glob(
            ".mainframe-backup-*"
        ))) == 1

        _success(fixture.run("--uninstall"))
        assert fixture.plugin.exists() is False
        assert backup.read_text() == "user data\n"
        assert index.is_file()
        assert memory.read_text() == "durable\n"


def test_uninstall_preserves_foreign_plugin_link() -> None:
    with _fixture() as fixture:
        foreign = fixture.root / "foreign/mainframe"
        _write(foreign / "plugin.json")
        fixture.plugin.parent.mkdir(parents=True)
        fixture.plugin.symlink_to(foreign)

        _success(fixture.run("--uninstall"))

        assert fixture.plugin.is_symlink()
        assert Path(os.readlink(fixture.plugin)) == foreign


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
