#!/usr/bin/env python3
"""Isolated dry-run contract tests for install.sh."""

from __future__ import annotations

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


def _write_executable(path: Path, exit_code: int = 0) -> None:
    _write(path, f"#!/bin/sh\nexit {exit_code}\n")
    path.chmod(0o755)


def _write_argument_check(path: Path, required: str) -> None:
    _write(path, (
        "#!/bin/sh\n"
        f"case \" $* \" in *\" {required} \"*) exit 0;; *) exit 64;; esac\n"
    ))
    path.chmod(0o755)


def _seed_repo(root: Path) -> Path:
    installer = root / "repo/install.sh"
    installer.parent.mkdir(parents=True)
    shutil.copy2(INSTALLER, installer)
    for relative in (
        "dist/claude-code/CLAUDE.md",
        "dist/claude-code/settings.json",
        "dist/claude-code/plugin/manifest.json",
        "dist/claude-code/output-styles/default.md",
        "dist/claude-code/scripts/secret",
        "dist/claude-code/templates/credentials-index.md",
    ):
        _write(installer.parent / relative)
    return installer


def _configure_fixture(
        repo: Path, fake_bin: Path, *, missing: str | None,
        empty: str | None, hidden_only: str | None,
        programs: tuple[str, ...], venv_exit: int | None,
        venv_requires: str | None, seed_dev: bool,
) -> None:
    for program in programs:
        _write_executable(fake_bin / program)
    if venv_exit is not None:
        _write_executable(repo / ".venv/bin/python3", venv_exit)
    if venv_requires is not None:
        _write_argument_check(repo / ".venv/bin/python3", venv_requires)
    if seed_dev:
        _write(repo / "dev/skills/harness-feedback/SKILL.md")
    if missing:
        path = repo / missing
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if empty:
        path = repo / empty
        shutil.rmtree(path)
        path.mkdir(parents=True)
    if hidden_only:
        path = repo / hidden_only
        shutil.rmtree(path)
        _write(path / ".hidden")


def _seed_uninstall_links(root: Path, repo: Path) -> tuple[Path, Path]:
    opencode_link = root / "config/opencode/AGENTS.md"
    style_link = root / "home/.claude/output-styles/old.md"
    opencode_link.parent.mkdir(parents=True)
    style_link.parent.mkdir(parents=True)
    opencode_link.symlink_to(repo / "dist/opencode/AGENTS.md")
    style_link.symlink_to(repo / "dist/claude-code/output-styles/old.md")
    return opencode_link, style_link


def _run_install(
        args: list[str], *, missing: str | None = None,
        empty: str | None = None, hidden_only: str | None = None,
        programs: tuple[str, ...] = (), venv_exit: int | None = None,
        venv_requires: str | None = None, seed_dev: bool = False,
        seed_uninstall_links: bool = False,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        repo = installer.parent
        home = root / "home"
        fake_bin = root / "bin"
        fake_bin.mkdir()
        _configure_fixture(
            repo, fake_bin, missing=missing, empty=empty,
            hidden_only=hidden_only, programs=programs, venv_exit=venv_exit,
            venv_requires=venv_requires, seed_dev=seed_dev,
        )
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "config"),
            "CODEX_HOME": str(root / "codex"),
            "PATH": f"{fake_bin}:{SYSTEM_PATH}",
        }
        uninstall_links = None
        if seed_uninstall_links:
            uninstall_links = _seed_uninstall_links(root, repo)
        result = subprocess.run(
            ["/bin/bash", str(installer), *args, "--dry-run"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if uninstall_links:
            opencode_link, style_link = uninstall_links
            assert opencode_link.is_symlink(), "dry-run removed OpenCode AGENTS.md"
            assert style_link.is_symlink(), "dry-run removed output style"
        else:
            assert not home.exists(), f"dry-run wrote into HOME: {list(home.rglob('*'))}"
        return result


def _assert_failed(result: subprocess.CompletedProcess[str], needle: str) -> None:
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert needle in output, output
    assert "Install complete" not in output


def test_missing_required_static_sources_fail() -> None:
    for relative in (
        "dist/claude-code/CLAUDE.md",
        "dist/claude-code/plugin",
        "dist/claude-code/output-styles",
        "dist/claude-code/scripts/secret",
        "dist/claude-code/templates/credentials-index.md",
    ):
        _assert_failed(_run_install([], missing=relative), relative)


def test_empty_required_directories_fail() -> None:
    for relative in (
        "dist/claude-code/plugin",
        "dist/claude-code/output-styles",
    ):
        _assert_failed(_run_install([], empty=relative), relative)


def test_hidden_only_item_directory_fails_but_whole_artifact_succeeds() -> None:
    _assert_failed(
        _run_install([], hidden_only="dist/claude-code/output-styles"),
        "dist/claude-code/output-styles",
    )
    result = _run_install([], hidden_only="dist/claude-code/plugin")
    assert result.returncode == 0, result.stdout + result.stderr


def test_dev_mode_requires_only_its_authored_source() -> None:
    _assert_failed(_run_install(["--dev"]), "dev/skills/harness-feedback")
    result = _run_install(["--dev"], seed_dev=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_requested_adapter_requires_its_executable() -> None:
    for flag, executable in (("--opencode", "opencode"), ("--codex", "codex")):
        _assert_failed(_run_install([flag], venv_exit=0), executable)


def test_requested_adapter_requires_repo_venv() -> None:
    for flag, executable in (("--opencode", "opencode"), ("--codex", "codex")):
        result = _run_install([flag], programs=(executable,))
        _assert_failed(result, ".venv")


def test_requested_adapter_generator_failure_reaches_exit_status() -> None:
    for flag, executable, generator in (
        ("--opencode", "opencode", "build_opencode.py"),
        ("--codex", "codex", "build_codex.py"),
    ):
        result = _run_install(
            [flag], programs=(executable,), venv_exit=42)
        _assert_failed(result, generator)
        output = result.stdout + result.stderr
        assert "would append source-line" in output
        assert "would install ruff" in output


def test_multiple_requested_failures_are_all_reported() -> None:
    result = _run_install(["--opencode", "--codex"], venv_exit=0)
    _assert_failed(result, "opencode not found")
    assert "codex not found" in result.stdout + result.stderr


def test_requested_adapter_success_preserves_completion() -> None:
    for flag, executable in (("--opencode", "opencode"), ("--codex", "codex")):
        result = _run_install([flag], programs=(executable,), venv_exit=0)
        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        assert "Install complete" in output


def test_codex_installer_requests_native_validation() -> None:
    result = _run_install(
        ["--codex"], programs=("codex",),
        venv_requires="--validate-native",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_optional_absences_preserve_success() -> None:
    result = _run_install([])
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Install complete" in output
    assert "dist/claude-code/rules" not in output
    assert "dev/skills/harness-feedback" not in output


def test_secret_bootstrap_sources_the_xdg_credentials_store() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        home = root / "home"
        xdg = root / "custom-config"
        (home / ".claude").mkdir(parents=True)
        _write(home / ".bashrc", "bash\n")
        _write(home / ".profile", "profile\n")
        text = installer.read_text().replace('\nmain "$@"\n', "\nbootstrap_secrets\n")
        installer.write_text(text)
        result = subprocess.run(
            ["/bin/bash", str(installer)],
            cwd=installer.parent,
            env={
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(xdg),
                "PATH": SYSTEM_PATH,
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        expected = (
            '[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env" ] '
            '&& set -a && . "${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env" '
            "&& set +a"
        )
        assert (xdg / "credentials").is_dir()
        for relative in (".zshenv", ".bashrc", ".profile"):
            assert expected in (home / relative).read_text()


def test_uninstall_bypasses_required_source_preflight() -> None:
    result = _run_install(
        ["--uninstall"], missing="dist/claude-code/output-styles",
        seed_uninstall_links=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Uninstall complete" in output
    assert "would remove symlink" in output
    assert "old.md" in output


def test_required_preflight_precedes_first_install_mutation() -> None:
    text = INSTALLER.read_text()
    main_start = text.index("main() {")
    uninstall_return = text.index("        return 0", main_start)
    preflight_call = "    if ! check_required_install_sources; then"
    assert preflight_call in text
    preflight = text.index(preflight_call, uninstall_return)
    cleanup = text.index("    cleanup_stale_post_migration", preflight)
    assert uninstall_return < preflight < cleanup


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
