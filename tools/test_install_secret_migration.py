#!/usr/bin/env python3
"""Isolated contracts for compatibility secret bootstrap and migration."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
SYSTEM_PATH = "/usr/bin:/bin"
LEGACY_MARKER = "# MAINFRAME hub: auto-source personal secrets store."
LEGACY_SOURCE = (
    '[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env" ] '
    '&& set -a && . "${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env" '
    "&& set +a"
)


def _write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode is not None:
        path.chmod(mode)


def _bootstrap_script(repo: Path) -> Path:
    repo.mkdir(parents=True)
    script = repo / "bootstrap-secrets.sh"
    text = INSTALLER.read_text().replace(
        '\nmain "$@"\n',
        "\nmigrate_legacy_secret_shell_exports\nbootstrap_secrets\n",
    )
    script.write_text(text)
    script.chmod(0o755)
    return script


def _fixture(root: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    repo = root / "repo"
    script = _bootstrap_script(repo)
    _write(repo / "dist/claude-code/scripts/secret", "#!/bin/sh\n", 0o755)
    _write(repo / "dist/claude-code/templates/credentials-index.md", "index\n")
    home = root / "home"
    (home / ".claude").mkdir(parents=True)
    config = root / "config"
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config),
        "PATH": SYSTEM_PATH,
    }
    return script, home, config, env


def _run(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(script)],
        cwd=script.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _run_uninstall(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    installer = repo / "install.sh"
    shutil.copy2(INSTALLER, installer)
    return subprocess.run(
        ["/bin/bash", str(installer), "--uninstall"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _legacy_rc(prefix: str, suffix: str) -> str:
    return f"{prefix}\n\n{LEGACY_MARKER}\n{LEGACY_SOURCE}\n{suffix}\n"


def test_bootstrap_removes_only_managed_shell_export_and_is_idempotent() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        script, home, config, env = _fixture(Path(temporary))
        expected: dict[Path, str] = {}
        for name in (".zshenv", ".bashrc", ".profile"):
            path = home / name
            _write(path, _legacy_rc(f"before-{name}", f"after-{name}"), 0o640)
            expected[path] = f"before-{name}\n\nafter-{name}\n"

        first = _run(script, env)
        assert first.returncode == 0, first.stdout + first.stderr
        second = _run(script, env)
        assert second.returncode == 0, second.stdout + second.stderr

        for path, content in expected.items():
            assert path.read_text() == content
            assert stat.S_IMODE(path.stat().st_mode) == 0o640
        assert (home / ".local/bin/secret").is_symlink()
        index = home / ".claude/credentials-index.md"
        assert index.read_text() == "index\n"
        assert stat.S_IMODE(index.stat().st_mode) == 0o600
        assert not list(home.rglob(".mainframe-shell-migration.*"))

        store = config / "credentials/secrets.env"
        _write(store, "UNRELATED_SECRET='must-not-be-inherited'\n", 0o600)
        shell = subprocess.run(
            ["/bin/zsh", "-c", 'test -z "${UNRELATED_SECRET+x}"'],
            env={
                "HOME": str(home),
                "ZDOTDIR": str(home),
                "XDG_CONFIG_HOME": str(config),
                "PATH": SYSTEM_PATH,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert shell.returncode == 0, shell.stdout + shell.stderr


def test_failed_migration_preserves_original_shell_file() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        script, home, _, env = _fixture(root)
        original = _legacy_rc("before", "after")
        zshenv = home / ".zshenv"
        _write(zshenv, original, 0o640)
        fake_bin = root / "bin"
        _write(fake_bin / "awk", "#!/bin/sh\nexit 73\n", 0o755)
        env["PATH"] = f"{fake_bin}:{SYSTEM_PATH}"

        result = _run(script, env)
        assert result.returncode != 0, result.stdout + result.stderr
        assert zshenv.read_text() == original
        assert stat.S_IMODE(zshenv.stat().st_mode) == 0o640
        assert not list(home.rglob(".mainframe-shell-migration.*"))


def test_symlinked_legacy_shell_file_blocks_migration_without_mutation() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        script, home, _, env = _fixture(root)
        target = root / "dotfiles/zshenv"
        original = _legacy_rc("before", "after")
        _write(target, original)
        zshenv = home / ".zshenv"
        zshenv.parent.mkdir(parents=True, exist_ok=True)
        zshenv.symlink_to(target)

        result = _run(script, env)
        output = result.stdout + result.stderr
        assert result.returncode != 0, output
        assert "legacy secrets source-line is inside symbolic-link shell file" in output
        assert zshenv.is_symlink()
        assert target.read_text() == original


def test_public_uninstall_migrates_legacy_shell_export_idempotently() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        script, home, _, env = _fixture(Path(temporary))
        repo = script.parent
        zshenv = home / ".zshenv"
        _write(zshenv, _legacy_rc("before", "after"), 0o640)

        first = _run_uninstall(repo, env)
        assert first.returncode == 0, first.stdout + first.stderr
        second = _run_uninstall(repo, env)
        assert second.returncode == 0, second.stdout + second.stderr
        assert zshenv.read_text() == "before\n\nafter\n"
        assert stat.S_IMODE(zshenv.stat().st_mode) == 0o640


def main() -> int:
    tests = [
        value for key, value in sorted(globals().items())
        if key.startswith("test_") and callable(value)
    ]
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
