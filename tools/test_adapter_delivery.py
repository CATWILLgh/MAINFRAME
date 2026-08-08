#!/usr/bin/env python3
"""Contract tests for adapter-scoped delivery.

Definition of done:
- the root installer is a no-op help entrypoint unless an adapter is selected;
- ``--claude`` routes through shared secrets and then the Claude Code adapter;
- Claude artifacts have one adapter-owned tree and no legacy root copies;
- ``/mainframe:init`` is user-only and absent from automatic model context;
- the credentials index has one gitignored repository location, seeded from a
  tracked adjacent template, while actual secret values stay unreadable.
"""

import json
import os
import pathlib
import stat
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROOT_INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "claude-code"
PLUGIN = ADAPTER / "plugin"
SHARED_CREDENTIALS = ROOT / "shared" / "credentials"


def _run_installer(*args, home=None):
    home = home or pathlib.Path(tempfile.mkdtemp())
    fake_bin = home / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    for command in (
        "ruff", "pip-audit", "semgrep", "osv-scanner", "oxlint",
        "depcruise", "knip", "fallow",
    ):
        executable = fake_bin / command
        executable.write_text("#!/bin/sh\necho test-version\n", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, HOME=str(home), PATH=f"{fake_bin}:/usr/bin:/bin")
    proc = subprocess.run(
        ["bash", str(ROOT_INSTALLER), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc, home


def test_root_without_arguments_is_help_only():
    proc, home = _run_installer()
    assert proc.returncode == 0
    assert "Usage:" in proc.stdout and "--claude" in proc.stdout
    assert sorted(home.iterdir()) == [home / "fake-bin"]


def test_root_dispatches_claude_dry_run():
    proc, _ = _run_installer("--claude", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "shared secrets" in proc.stdout.lower()
    assert "claude code adapter" in proc.stdout.lower()


def test_claude_uninstall_preserves_shared_secrets():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    helper = home / ".local" / "bin" / "secret"
    assert helper.is_symlink()
    assert (home / ".claude" / "CLAUDE.md").is_symlink()

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert helper.is_symlink()
    assert not (home / ".claude" / "CLAUDE.md").exists()


def test_adapter_owns_claude_artifacts():
    assert (ADAPTER / "install.sh").is_file()
    assert (ADAPTER / "export" / "CLAUDE.md").is_file()
    assert (PLUGIN / ".claude-plugin" / "plugin.json").is_file()
    assert not (ROOT / "export").exists()
    assert not (ROOT / "plugin-dist").exists()


def test_umbrella_has_no_delivery_metadata_comment():
    umbrella = (ADAPTER / "export" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Source of truth:" not in umbrella
    assert "This file is symlinked" not in umbrella


def test_init_skill_is_manual_only():
    skill = PLUGIN / "skills" / "init" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "name: init" in body
    assert "disable-model-invocation: true" in body
    assert "context: fork" not in body


def test_shared_secrets_have_one_runtime_index():
    assert (SHARED_CREDENTIALS / "install.sh").is_file()
    assert (SHARED_CREDENTIALS / "secret").is_file()
    assert (SHARED_CREDENTIALS / "credentials-index.template.md").is_file()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "shared/credentials/credentials-index.md"],
        cwd=ROOT,
    )
    assert ignored.returncode == 0


def test_claude_permissions_expose_only_helper_and_index():
    settings = json.loads((ADAPTER / "export" / "settings.json").read_text())
    allowed = settings["permissions"]["allow"]
    denied = settings["permissions"]["deny"]
    assert "Bash(secret *)" in allowed
    assert "Read(~/Documents/projects/MAINFRAME/shared/credentials/credentials-index.md)" in allowed
    assert "Read(~/.config/credentials/**)" in denied
    assert "Read(**/secrets/**)" in denied


def _run_all():
    import sys
    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
