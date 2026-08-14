#!/usr/bin/env python3
"""Contract tests for the first native Codex adapter baseline."""

import os
import pathlib
import stat
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "codex"
SHARED = ROOT / "shared" / "credentials"


def _run(*args, home=None):
    home = home or pathlib.Path(tempfile.mkdtemp())
    fake_bin = home / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    codex = fake_bin / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = --version ]; then echo 'codex-cli 0.147.0'; fi\n",
        encoding="utf-8",
    )
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, HOME=str(home), PATH=f"{fake_bin}:/usr/bin:/bin")
    proc = subprocess.run(
        ["bash", str(INSTALLER), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc, home


def test_root_help_exposes_codex_without_installing_it():
    proc, home = _run()
    assert proc.returncode == 0, proc.stderr
    assert "--codex" in proc.stdout
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_dry_run_reports_direct_cross_surface_delivery():
    proc, home = _run("--codex", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "regular file" in proc.stdout
    assert "mainframe-init" in proc.stdout
    assert "mainframe-secrets" in proc.stdout
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_clean_install_is_idempotent_and_uninstall_preserves_shared_secrets():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr

    codex_dir = home / ".codex"
    agents = codex_dir / "AGENTS.md"
    state = codex_dir / ".mainframe-agents-state"
    index_state = codex_dir / ".mainframe-index-state"
    assert agents.is_file() and not agents.is_symlink()
    assert agents.read_bytes() == (ADAPTER / "export" / "AGENTS.md").read_bytes()
    assert state.is_file()
    assert stat.S_IMODE(agents.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.stat().st_mode) == 0o600

    for name in ("mainframe-init", "mainframe-secrets"):
        target = home / ".agents" / "skills" / name
        assert target.is_symlink()
        assert target.resolve() == ADAPTER / "skills" / name

    index = codex_dir / "credentials-index.md"
    helper = home / ".local" / "bin" / "secret"
    assert index.is_symlink() and index.resolve() == SHARED / "credentials-index.md"
    assert index_state.is_file()
    assert helper.is_symlink()
    assert not (codex_dir / "config.toml").exists()

    reinstalled, _ = _run("--codex", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert not agents.exists()
    assert not state.exists()
    assert not index.exists() and not index.is_symlink()
    assert not index_state.exists()
    assert helper.is_symlink()
    for name in ("mainframe-init", "mainframe-secrets"):
        target = home / ".agents" / "skills" / name
        assert not target.exists() and not target.is_symlink()


def test_existing_global_agents_requires_explicit_backed_up_replacement():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    target = codex_dir / "AGENTS.md"
    target.write_text("personal instructions\n", encoding="utf-8")

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "unmanaged global AGENTS.md" in refused.stderr
    assert target.read_text(encoding="utf-8") == "personal instructions\n"
    assert not (home / ".local" / "bin" / "secret").exists()

    installed, _ = _run("--codex", "--yes", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.read_bytes() == (ADAPTER / "export" / "AGENTS.md").read_bytes()
    backups = list(codex_dir.glob("AGENTS.md.backup-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "personal instructions\n"

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.read_text(encoding="utf-8") == "personal instructions\n"
    assert not backups[0].exists()


def test_changed_managed_agents_is_preserved_on_uninstall():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "AGENTS.md"
    target.write_text("user changed this file\n", encoding="utf-8")

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "changed after installation" in removed.stderr
    assert target.read_text(encoding="utf-8") == "user changed this file\n"


def test_existing_codex_index_requires_yes_and_is_restored():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    index = codex_dir / "credentials-index.md"
    index.write_text("old local index\n", encoding="utf-8")

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "credentials index already exists" in refused.stderr
    assert index.read_text(encoding="utf-8") == "old local index\n"
    assert not (home / ".local" / "bin" / "secret").exists()

    installed, _ = _run("--codex", "--yes", home=home)
    assert installed.returncode == 0, installed.stderr
    assert index.is_symlink() and index.resolve() == SHARED / "credentials-index.md"

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert index.is_file() and not index.is_symlink()
    assert index.read_text(encoding="utf-8") == "old local index\n"


def test_skill_collision_stops_before_shared_install():
    home = pathlib.Path(tempfile.mkdtemp())
    collision = home / ".agents" / "skills" / "mainframe-init"
    collision.mkdir(parents=True)
    (collision / "SKILL.md").write_text("unrelated\n", encoding="utf-8")

    proc, _ = _run("--codex", home=home)
    assert proc.returncode != 0
    assert "existing skill path" in proc.stderr
    assert not (home / ".local" / "bin" / "secret").exists()
    assert (collision / "SKILL.md").read_text(encoding="utf-8") == "unrelated\n"


def test_unsupported_dev_mode_fails_before_any_delivery():
    proc, home = _run("--codex", "--dev")
    assert proc.returncode == 2
    assert "not implemented yet" in proc.stderr
    assert not (home / ".codex").exists()
    assert not (home / ".local" / "bin" / "secret").exists()


def test_baseline_uses_native_standalone_layers_only():
    assert not (ADAPTER / "plugin").exists()
    assert not (ADAPTER / "hooks").exists()
    assert not (ADAPTER / "agents").exists()
    assert not (ADAPTER / "config.toml").exists()

    init_metadata = (
        ADAPTER / "skills" / "mainframe-init" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in init_metadata
    assert "/goal" not in (
        ADAPTER / "skills" / "mainframe-init" / "SKILL.md"
    ).read_text(encoding="utf-8")


def _run_all():
    failures = 0
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
