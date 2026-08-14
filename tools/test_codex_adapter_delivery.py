#!/usr/bin/env python3
"""Contract tests for the first native Codex adapter baseline."""

import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import tomllib


ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "codex"
SHARED = ROOT / "shared" / "credentials"
CONFIG_MANAGER = ADAPTER / "scripts" / "manage-config.py"
CONFIG_SOURCE = ADAPTER / "config" / "mainframe-permissions.toml"
REQUIREMENTS_SOURCE = ADAPTER / "config" / "mainframe-requirements.toml"


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
    requirements = home / "etc" / "codex" / "requirements.toml"
    env = dict(
        os.environ,
        HOME=str(home),
        PATH=f"{fake_bin}:/usr/bin:/bin",
        CODEX_REQUIREMENTS_FILE=str(requirements),
    )
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
    assert "mainframe.rules" in proc.stdout
    assert "permissions" in proc.stdout
    assert "profile allowlist" in proc.stdout
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
    rules = codex_dir / "rules" / "mainframe.rules"
    rules_state = codex_dir / ".mainframe-rules-state"
    assert rules.is_symlink() and rules.resolve() == ADAPTER / "rules" / "mainframe.rules"
    assert rules_state.is_file()
    config = codex_dir / "config.toml"
    config_state = codex_dir / ".mainframe-config-state.json"
    assert config.is_file() and config_state.is_file()
    config_data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert config_data["default_permissions"] == "mainframe"
    assert config_data["approval_policy"] == "on-request"
    assert config_data["approvals_reviewer"] == "auto_review"
    assert config_data["shell_environment_policy"]["inherit"] == "core"
    assert config_data["permissions"]["mainframe"]["extends"] == ":workspace"
    assert config_data["permissions"]["mainframe"]["filesystem"]["~/.config/credentials"] == "deny"
    assert config_data["permissions"]["mainframe"]["network"]["domains"] == {
        "localhost": "allow",
        "127.0.0.1": "allow",
        "::1": "allow",
    }
    assert config_data["permissions"]["mainframe"]["network"]["unix_sockets"] == {
        "/tmp/.s.PGSQL.5432": "allow"
    }
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_state.stat().st_mode) == 0o600
    requirements = home / "etc" / "codex" / "requirements.toml"
    requirements_state = requirements.parent / ".mainframe-requirements-state.json"
    requirements_data = tomllib.loads(requirements.read_text(encoding="utf-8"))
    assert requirements_data["allowed_permission_profiles"] == {
        ":read-only": True,
        ":workspace": True,
        ":danger-full-access": True,
        "mainframe": True,
    }
    assert stat.S_IMODE(requirements.stat().st_mode) == 0o644
    assert stat.S_IMODE(requirements_state.stat().st_mode) == 0o644
    assert helper.is_symlink()

    reinstalled, _ = _run("--codex", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert not agents.exists()
    assert not state.exists()
    assert not index.exists() and not index.is_symlink()
    assert not index_state.exists()
    assert not rules.exists() and not rules.is_symlink()
    assert not rules_state.exists()
    assert not config.exists()
    assert not config_state.exists()
    assert not requirements.exists()
    assert not requirements_state.exists()
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


def test_existing_mainframe_rules_require_yes_and_are_restored():
    home = pathlib.Path(tempfile.mkdtemp())
    rules_dir = home / ".codex" / "rules"
    rules_dir.mkdir(parents=True)
    target = rules_dir / "mainframe.rules"
    target.write_text("# user-owned rules\n", encoding="utf-8")

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "MAINFRAME rules file already exists" in refused.stderr
    assert target.read_text(encoding="utf-8") == "# user-owned rules\n"

    installed, _ = _run("--codex", "--yes", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.is_symlink() and target.resolve() == ADAPTER / "rules" / "mainframe.rules"

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.is_file() and not target.is_symlink()
    assert target.read_text(encoding="utf-8") == "# user-owned rules\n"


def test_changed_mainframe_rules_stop_uninstall_before_other_removal():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "rules" / "mainframe.rules"
    target.unlink()
    target.write_text("# changed after install\n", encoding="utf-8")

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "rules installation changed" in removed.stderr
    assert target.read_text(encoding="utf-8") == "# changed after install\n"
    assert (home / ".codex" / "AGENTS.md").is_file()
    assert (home / ".agents" / "skills" / "mainframe-init").is_symlink()


def test_existing_config_is_merged_and_uninstall_restores_only_displaced_settings():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    config = codex_dir / "config.toml"
    config.write_text(
        'model = "example"\n'
        'approval_policy = "on-request"\n'
        'approvals_reviewer = "auto_review"\n'
        'sandbox_mode = "workspace-write"\n\n'
        '[mcp_servers.example]\n'
        'command = "example"\n\n'
        '[shell_environment_policy.set]\n'
        'EXAMPLE = "kept"\n',
        encoding="utf-8",
    )

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert "sandbox_mode" not in data
    assert data["default_permissions"] == "mainframe"
    assert data["mcp_servers"]["example"]["command"] == "example"
    backups = list(codex_dir.glob("config.toml.backup-*"))
    assert len(backups) == 1
    assert 'sandbox_mode = "workspace-write"' in backups[0].read_text(encoding="utf-8")

    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n[desktop]\ntheme = "dark"\n')

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    restored = tomllib.loads(config.read_text(encoding="utf-8"))
    assert restored["sandbox_mode"] == "workspace-write"
    assert restored["approval_policy"] == "on-request"
    assert restored["approvals_reviewer"] == "auto_review"
    assert restored["desktop"]["theme"] == "dark"
    assert "default_permissions" not in restored
    assert backups[0].exists()


def test_existing_unrelated_requirements_are_preserved_on_uninstall():
    home = pathlib.Path(tempfile.mkdtemp())
    requirements = home / "etc" / "codex" / "requirements.toml"
    requirements.parent.mkdir(parents=True)
    requirements.write_text(
        'allowed_approval_policies = ["on-request"]\n',
        encoding="utf-8",
    )

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    data = tomllib.loads(requirements.read_text(encoding="utf-8"))
    assert data["allowed_approval_policies"] == ["on-request"]
    assert data["allowed_permission_profiles"]["mainframe"] is True

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert requirements.read_text(encoding="utf-8") == 'allowed_approval_policies = ["on-request"]\n'


def test_existing_permission_profile_allowlist_stops_before_delivery():
    home = pathlib.Path(tempfile.mkdtemp())
    requirements = home / "etc" / "codex" / "requirements.toml"
    requirements.parent.mkdir(parents=True)
    original = '[allowed_permission_profiles]\n":workspace" = true\n'
    requirements.write_text(original, encoding="utf-8")

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "unmanaged allowed_permission_profiles" in refused.stderr
    assert requirements.read_text(encoding="utf-8") == original
    assert not (home / ".codex").exists()


def test_changed_profile_allowlist_stops_uninstall_before_other_removal():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    requirements = home / "etc" / "codex" / "requirements.toml"
    requirements.write_text(
        requirements.read_text(encoding="utf-8").replace(
            "mainframe = true",
            "mainframe = false",
        ),
        encoding="utf-8",
    )

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "allowlist changed" in removed.stderr
    assert (home / ".codex" / "AGENTS.md").is_file()


def test_unmanaged_mainframe_permission_profile_stops_before_delivery():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    config = codex_dir / "config.toml"
    config.write_text(
        '[permissions.mainframe]\nextends = ":read-only"\n',
        encoding="utf-8",
    )

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "unmanaged permissions.mainframe" in refused.stderr
    assert config.read_text(encoding="utf-8") == '[permissions.mainframe]\nextends = ":read-only"\n'
    assert not (home / ".local" / "bin" / "secret").exists()


def test_changed_permissions_block_is_preserved_on_uninstall():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    config = home / ".codex" / "config.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'default_permissions = "mainframe"',
            'default_permissions = ":danger-full-access"',
        ),
        encoding="utf-8",
    )

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "permissions block changed" in removed.stderr
    assert ':danger-full-access' in config.read_text(encoding="utf-8")
    assert (home / ".codex" / "AGENTS.md").is_file()


def test_owned_permissions_block_can_evolve_without_replacing_user_config():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    codex_dir = home / ".codex"
    config = codex_dir / "config.toml"
    source = home / "updated-permissions.toml"
    source.write_text(
        CONFIG_SOURCE.read_text(encoding="utf-8").replace(
            "Workspace editing with protected credentials and reviewed external access.",
            "Updated owned profile.",
        ),
        encoding="utf-8",
    )
    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n[desktop]\ntheme = "kept"\n')

    updated = subprocess.run(
        [
            sys.executable,
            str(CONFIG_MANAGER),
            "install",
            "--config",
            str(config),
            "--source",
            str(source),
            "--repo-root",
            str(ROOT),
            "--state",
            str(codex_dir / ".mainframe-config-state.json"),
            "--backup",
            str(codex_dir / "unused-backup"),
        ],
        capture_output=True,
        text=True,
    )
    assert updated.returncode == 0, updated.stderr
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert data["permissions"]["mainframe"]["description"] == "Updated owned profile."
    assert data["desktop"]["theme"] == "kept"


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
    assert (ADAPTER / "rules" / "mainframe.rules").is_file()
    assert 'pattern = ["secret"]' in (
        ADAPTER / "rules" / "mainframe.rules"
    ).read_text(encoding="utf-8")
    assert (ADAPTER / "config" / "mainframe-permissions.toml").is_file()
    assert REQUIREMENTS_SOURCE.is_file()
    assert (ADAPTER / "scripts" / "manage-config.py").is_file()
    assert (ADAPTER / "scripts" / "manage-requirements.py").is_file()

    init_metadata = (
        ADAPTER / "skills" / "mainframe-init" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in init_metadata
    assert "/goal" not in (
        ADAPTER / "skills" / "mainframe-init" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_shared_judgment_and_primary_completion_are_separated():
    global_body = (ADAPTER / "export" / "AGENTS.md").read_text(encoding="utf-8")
    normalized_global = " ".join(global_body.split())
    assert "accurate unfavorable finding" in normalized_global
    assert "Before a consequential action" in normalized_global
    assert "smallest adequate check" in normalized_global
    assert "narrow green check" in normalized_global
    assert "TODOs" not in global_body
    assert "plain language" not in global_body

    init_body = (
        ADAPTER / "skills" / "mainframe-init" / "SKILL.md"
    ).read_text(encoding="utf-8")
    normalized_init = " ".join(init_body.split())
    assert "technical detail into practical consequences" in normalized_init
    assert "safest practical path" in normalized_init
    assert "When implementing directly" in normalized_init
    assert "deferred in-scope work as a substitute" in normalized_init


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
