#!/usr/bin/env python3
"""Public temporary-home lifecycle contracts for Claude Code and Codex."""

from __future__ import annotations

import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
SYSTEM_PATH = "/usr/bin:/bin"
FIXED_TIMESTAMP = "20260804-120000"
TOOL_BINARIES = (
    "ruff", "pip-audit", "semgrep", "osv-scanner", "oxlint",
    "depcruise", "knip", "fallow",
)


def _write(path: Path, text: str = "fixture\n", mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode is not None:
        path.chmod(mode)


def _executable(path: Path, exit_code: int = 0) -> None:
    _write(path, f"#!/bin/sh\nexit {exit_code}\n", 0o755)


def _seed_repo(root: Path, generator_exit: int) -> Path:
    repo = root / "repo"
    repo.mkdir()
    shutil.copy2(INSTALLER, repo / "install.sh")
    for relative in (
        "dist/claude-code/CLAUDE.md",
        "dist/claude-code/settings.json",
        "dist/claude-code/plugin/manifest.json",
        "dist/claude-code/plugin/skills/surface-ticket/SKILL.md",
        "dist/claude-code/output-styles/default.md",
        "dist/claude-code/scripts/secret",
        "dist/claude-code/templates/credentials-index.md",
        "dist/codex/bundle-v2/AGENTS.md",
        "dist/codex/bundle-v2/credentials-index.md",
        "dist/codex/bundle-v2/hooks.json",
        "dist/codex/bundle-v2/mainframe-hook.sh",
        "dist/codex/bundle-v2/rules/mainframe.rules",
        "dist/codex/bundle-v2/skills/surface-ticket/SKILL.md",
        "dist/codex/bundle-v2/mainframe-agent-methods/decision-review/SKILL.md",
        "dist/codex/bundle-v2/agents/reviewer.toml",
        "dist/codex/bundle-v2/gates/detectors/path-validation.py",
        "dist/codex/bundle-v2/gates/rules/bash.json",
    ):
        _write(repo / relative)
    _executable(repo / ".venv/bin/python3", generator_exit)
    return repo


@dataclass(frozen=True)
class Fixture:
    root: Path
    repo: Path
    home: Path
    codex: Path
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


def _fixture(root: Path, generator_exit: int = 0) -> Fixture:
    repo = _seed_repo(root, generator_exit)
    home = root / "home"
    codex = root / "codex"
    fake_bin = root / "bin"
    fake_bin.mkdir()
    _executable(fake_bin / "codex")
    for binary in TOOL_BINARIES:
        _executable(fake_bin / binary)
    _write(fake_bin / "date", f"#!/bin/sh\nprintf '%s\\n' '{FIXED_TIMESTAMP}'\n", 0o755)
    return Fixture(
        root=root,
        repo=repo,
        home=home,
        codex=codex,
        env={
            "HOME": str(home),
            "CODEX_HOME": str(codex),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_STATE_HOME": str(root / "state"),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        },
    )


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def _assert_link(path: Path, target: Path) -> None:
    assert path.is_symlink(), path
    assert path.resolve() == target.resolve()


def _assert_installed(fixture: Fixture) -> None:
    claude = fixture.home / ".claude"
    _assert_link(claude / "CLAUDE.md", fixture.repo / "dist/claude-code/CLAUDE.md")
    _assert_link(claude / "settings.json", fixture.repo / "dist/claude-code/settings.json")
    _assert_link(claude / "skills/mainframe", fixture.repo / "dist/claude-code/plugin")
    _assert_link(
        claude / "output-styles/default.md",
        fixture.repo / "dist/claude-code/output-styles/default.md",
    )
    _assert_link(
        fixture.home / ".local/bin/secret",
        fixture.repo / "dist/claude-code/scripts/secret",
    )
    _assert_link(
        fixture.codex / "AGENTS.md",
        fixture.repo / "dist/codex/bundle-v2/AGENTS.md",
    )
    _assert_link(
        fixture.codex / "skills/surface-ticket",
        fixture.repo / "dist/codex/bundle-v2/skills/surface-ticket",
    )
    _assert_link(
        fixture.codex / "mainframe-agent-methods/decision-review",
        fixture.repo / "dist/codex/bundle-v2/mainframe-agent-methods/decision-review",
    )
    _assert_link(
        fixture.codex / "rules/mainframe.rules",
        fixture.repo / "dist/codex/bundle-v2/rules/mainframe.rules",
    )
    _assert_link(
        fixture.codex / "hooks.json",
        fixture.repo / "dist/codex/bundle-v2/hooks.json",
    )
    _assert_link(
        fixture.codex / "mainframe-hook.sh",
        fixture.repo / "dist/codex/bundle-v2/mainframe-hook.sh",
    )
    _assert_link(
        fixture.codex / "gates/detectors",
        fixture.repo / "dist/codex/bundle-v2/gates/detectors",
    )
    _assert_link(
        fixture.codex / "gates/rules",
        fixture.repo / "dist/codex/bundle-v2/gates/rules",
    )
    _assert_link(
        fixture.codex / "agents/reviewer.toml",
        fixture.repo / "dist/codex/bundle-v2/agents/reviewer.toml",
    )
    for index in (
        claude / "credentials-index.md",
        fixture.codex / "credentials-index.md",
    ):
        assert index.is_file() and not index.is_symlink()
        assert stat.S_IMODE(index.stat().st_mode) == 0o600
    assert not (fixture.root / "config/opencode").exists()
    assert not (fixture.home / ".gemini").exists()


def test_install_repeat_uninstall_reinstall_preserves_user_state() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        fixture = _fixture(Path(temporary))
        claude = fixture.home / ".claude"
        fixture.codex.mkdir(parents=True)
        _write(claude / "CLAUDE.md", "foreign claude\n")
        _write(fixture.codex / "AGENTS.md", "foreign codex\n")

        _assert_success(fixture.run("--codex"))
        _assert_installed(fixture)
        assert (claude / f"CLAUDE.md.backup-{FIXED_TIMESTAMP}").read_text() == "foreign claude\n"
        assert (fixture.codex / f"AGENTS.md.backup-{FIXED_TIMESTAMP}").read_text() == "foreign codex\n"
        _write(claude / "credentials-index.md", "user claude index\n", 0o600)
        _write(fixture.codex / "credentials-index.md", "user codex index\n", 0o600)
        _write(claude / "output-styles/user.md", "user style\n")
        _write(fixture.codex / "skills/user-skill/SKILL.md", "user skill\n")

        _assert_success(fixture.run("--codex"))
        _assert_installed(fixture)
        assert len(list(claude.glob("CLAUDE.md.backup-*"))) == 1
        assert len(list(fixture.codex.glob("AGENTS.md.backup-*"))) == 1

        _assert_success(fixture.run("--uninstall"))
        for path in (
            claude / "CLAUDE.md",
            claude / "settings.json",
            claude / "skills/mainframe",
            claude / "output-styles/default.md",
            fixture.home / ".local/bin/secret",
            fixture.codex / "AGENTS.md",
            fixture.codex / "skills/surface-ticket",
            fixture.codex / "mainframe-agent-methods/decision-review",
            fixture.codex / "rules/mainframe.rules",
            fixture.codex / "hooks.json",
            fixture.codex / "mainframe-hook.sh",
            fixture.codex / "gates/detectors",
            fixture.codex / "gates/rules",
            fixture.codex / "agents/reviewer.toml",
        ):
            assert not path.exists() and not path.is_symlink(), path
        assert (claude / "credentials-index.md").read_text() == "user claude index\n"
        assert (fixture.codex / "credentials-index.md").read_text() == "user codex index\n"
        assert (claude / "output-styles/user.md").read_text() == "user style\n"
        assert (fixture.codex / "skills/user-skill/SKILL.md").read_text() == "user skill\n"

        _assert_success(fixture.run("--codex"))
        _assert_installed(fixture)
        assert (claude / "credentials-index.md").read_text() == "user claude index\n"
        assert (fixture.codex / "credentials-index.md").read_text() == "user codex index\n"


def test_codex_generation_failure_precedes_home_mutation() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        fixture = _fixture(Path(temporary), generator_exit=42)
        result = fixture.run("--codex")
        output = result.stdout + result.stderr
        assert result.returncode != 0, output
        assert "Codex bundle projection failed" in output
        assert not fixture.home.exists(), list(fixture.home.rglob("*"))
        assert not fixture.codex.exists(), list(fixture.codex.rglob("*"))


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
