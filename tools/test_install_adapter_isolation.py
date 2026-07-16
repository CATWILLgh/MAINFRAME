#!/usr/bin/env python3
"""Filesystem contracts for isolated legacy adapter delivery."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
SYSTEM_PATH = "/usr/bin:/bin"


def _write(path: Path, text: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _executable(path: Path) -> None:
    _write(path, "#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


def _script(repo: Path, call: str) -> Path:
    target = repo / f"{call}.sh"
    text = INSTALLER.read_text().replace('\nmain "$@"\n', f"\n{call}\n")
    target.write_text(text)
    target.chmod(0o755)
    return target


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


def test_opencode_upgrade_backup_and_uninstall_stay_in_opencode() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        bundle = repo / "dist/opencode/bundle-v2"
        for relative in (
            "AGENTS.md",
            "credentials-index.md",
            "agents/main.md",
            "gates/detectors/gate.py",
            "memory/store.py",
            "plugins/mainframe-memory.js",
            "skills/task-workflow/SKILL.md",
        ):
            _write(bundle / relative)
        legacy = repo / "adapters/opencode/plugins/mainframe-memory.js"
        _write(legacy)
        _executable(repo / ".venv/bin/python3")
        fake_bin = root / "bin"
        fake_bin.mkdir()
        _executable(fake_bin / "opencode")
        home = root / "home"
        config = root / "config/opencode"
        data = root / "data/opencode/mainframe-memory"
        _write(data / "MEMORY.md", "durable\n")
        _write(config / "plugins/user.js", "user\n")
        legacy_link = config / "plugins/mainframe-memory.js"
        legacy_link.symlink_to(legacy)
        redirected = home / ".claude/opencode-gates"
        _write(redirected / "foreign.py", "foreign\n")
        (config / "gates").symlink_to(redirected)
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        }

        installed = _run(_script(repo, "install_opencode"), env)
        assert installed.returncode == 0, installed.stdout + installed.stderr
        plugin = config / "plugins/mainframe-memory.js"
        assert plugin.resolve() == (bundle / "plugins/mainframe-memory.js")
        backups = list(config.glob(
            ".mainframe-backup-*/plugins/mainframe-memory.js"))
        assert len(backups) == 1 and backups[0].is_symlink()
        assert (config / "plugins/user.js").read_text() == "user\n"
        index = config / "credentials-index.md"
        assert index.read_text() == "fixture\n"
        assert index.stat().st_mode & 0o777 == 0o600
        assert (data / "MEMORY.md").read_text() == "durable\n"
        assert not (config / "gates").is_symlink()
        assert (redirected / "foreign.py").read_text() == "foreign\n"

        removed = _run(_script(repo, "uninstall_opencode"), env)
        assert removed.returncode == 0, removed.stdout + removed.stderr
        assert not plugin.exists()
        assert (config / "plugins/user.js").is_file()
        assert index.is_file()
        assert (data / "MEMORY.md").is_file()
        assert backups[0].is_symlink()


def test_codex_installs_its_own_gate_tree() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        bundle = repo / "dist/codex/bundle-v2"
        for relative in (
            "AGENTS.md",
            "credentials-index.md",
            "hooks.json",
            "mainframe-hook.sh",
            "rules/mainframe.rules",
            "skills/task-workflow/SKILL.md",
            "agents/reviewer.toml",
            "gates/detectors/path-validation.py",
            "gates/rules/bash.json",
        ):
            _write(bundle / relative)
        _executable(repo / ".venv/bin/python3")
        fake_bin = root / "bin"
        fake_bin.mkdir()
        _executable(fake_bin / "codex")
        home = root / "home"
        codex_home = root / "codex"
        redirected = home / ".claude/codex-gates"
        _write(redirected / "foreign.py", "foreign\n")
        codex_home.mkdir()
        (codex_home / "gates").symlink_to(redirected)
        env = {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        }

        result = _run(_script(repo, "install_codex"), env)
        assert result.returncode == 0, result.stdout + result.stderr
        detector = codex_home / "gates/detectors/path-validation.py"
        assert detector.resolve() == bundle / "gates/detectors/path-validation.py"
        assert not (codex_home / "gates").is_symlink()
        assert (redirected / "foreign.py").read_text() == "foreign\n"
        index = codex_home / "credentials-index.md"
        assert index.read_text() == "fixture\n"
        assert index.stat().st_mode & 0o777 == 0o600


def test_uninstall_does_not_follow_redirected_adapter_directory() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        source = repo / "dist/opencode/bundle-v2/skills/task-workflow"
        _write(source / "SKILL.md")
        home = root / "home"
        config = root / "config/opencode"
        redirected = home / ".claude/opencode-skills"
        redirected.mkdir(parents=True)
        managed = redirected / "task-workflow"
        managed.symlink_to(source)
        config.mkdir(parents=True)
        (config / "skills").symlink_to(redirected)
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "PATH": SYSTEM_PATH,
        }

        removed = _run(_script(repo, "uninstall_opencode"), env)
        assert removed.returncode == 0, removed.stdout + removed.stderr
        assert managed.is_symlink()
        assert managed.resolve() == source


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
