#!/usr/bin/env python3
"""Contract tests for adapter-scoped delivery.

Definition of done:
- the root installer is a no-op help entrypoint unless an adapter is selected;
- ``--claude`` routes through shared secrets and then the Claude Code adapter;
- Claude artifacts have one adapter-owned tree and no legacy root copies;
- specialists are delivered as user-level ``mainframe-*`` agents, outside the
  plugin boundary that drops agent-scoped hooks, MCP servers, and permissions;
- mutable Claude user settings remain a regular local file: MAINFRAME merges
  owned policy and initial defaults, preserves user changes, and removes only
  recorded ownership on uninstall;
- ``/mainframe:init`` is user-only and absent from automatic model context;
- the old automatic task workflow and its reminder hooks are not shipped;
- the credentials index has one gitignored repository location, seeded from a
  tracked adjacent template, while actual secret values stay unreadable.
"""

import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROOT_INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "claude-code"
PLUGIN = ADAPTER / "plugin"
AGENTS = ADAPTER / "agents"
SHARED_CREDENTIALS = ROOT / "shared" / "credentials"
ADAPTER_INSTALLER = ADAPTER / "install.sh"
SETTINGS_MANAGER = ADAPTER / "settings-manager.py"
MANAGED_DELIVERY = ROOT / "shared" / "managed-delivery" / "manage-artifact.py"
MIN_CLAUDE_VERSION = re.search(
    r'^MIN_CLAUDE_VERSION="([0-9]+\.[0-9]+\.[0-9]+)"$',
    ADAPTER_INSTALLER.read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)


def _run_installer(
    *args, home=None, claude_version=None, broken_python=False, codex_peer=False
):
    home = home or pathlib.Path(tempfile.mkdtemp())
    fake_bin = home / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    version_file = home / "claude-version"
    version_file.write_text(claude_version or MIN_CLAUDE_VERSION, encoding="utf-8")
    claude = fake_bin / "claude"
    claude.write_text(
        "#!/bin/sh\n"
        f"version_file='{version_file}'\n"
        f"minimum='{MIN_CLAUDE_VERSION}'\n"
        "case \"${1:-}\" in\n"
        "  --version|-v) printf '%s (Claude Code)\\n' \"$(cat \"$version_file\")\" ;;\n"
        "  update|upgrade) printf '%s' \"$minimum\" > \"$version_file\"; echo updated ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR)
    if codex_peer:
        codex = fake_bin / "codex"
        codex.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = login ] && [ \"${2:-}\" = status ]; then exit 0; fi\n"
            "if [ \"${1:-}\" = --version ]; then echo 'codex-cli 0.147.0'; exit 0; fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        codex.chmod(codex.stat().st_mode | stat.S_IXUSR)
    if broken_python:
        python = fake_bin / "python3"
        python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
    for command in ("ruff", "oxlint"):
        executable = fake_bin / command
        executable.write_text("#!/bin/sh\necho test-version\n", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    env = dict(
        os.environ,
        HOME=str(home),
        PATH=f"{fake_bin}:/usr/bin:/bin",
        MAINFRAME_INSTALL_TESTING="1",
    )
    proc = subprocess.run(
        ["bash", str(ROOT_INSTALLER), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc, home


def _run_settings_manager(action, source, target, state, backup, *args):
    return subprocess.run(
        [
            sys.executable,
            str(SETTINGS_MANAGER),
            action,
            "--source", str(source),
            "--target", str(target),
            "--state", str(state),
            "--backup", str(backup),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_root_without_arguments_is_help_only():
    proc, home = _run_installer()
    assert proc.returncode == 0
    assert "Usage:" in proc.stdout and "--claude" in proc.stdout
    assert sorted(home.iterdir()) == [home / "claude-version", home / "fake-bin"]


def test_root_dispatches_claude_dry_run():
    proc, _ = _run_installer("--claude", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "shared secrets" in proc.stdout.lower()
    assert "claude code adapter" in proc.stdout.lower()


def test_peer_advisor_is_explicit_optional_and_reversible():
    missing, missing_home = _run_installer("--claude", "--with-peer-advisor")
    assert missing.returncode != 0
    assert "requires the Codex CLI" in missing.stderr
    assert not (missing_home / ".claude" / "skills" / "mainframe-peer-review").exists()

    installed, home = _run_installer(
        "--claude", "--with-peer-advisor", codex_peer=True
    )
    assert installed.returncode == 0, installed.stderr
    target = home / ".claude" / "skills" / "mainframe-peer-review"
    assert target.is_dir() and not target.is_symlink()
    body = (target / "SKILL.md").read_text(encoding="utf-8")
    assert "codex exec --ignore-user-config" in body
    assert "never use `--last`" in body
    assert "allowed-tools: Bash(codex *)," in body

    plain, _ = _run_installer("--claude", home=home, codex_peer=True)
    assert plain.returncode == 0, plain.stderr
    assert not target.exists()


def test_reinstall_removes_unchanged_retired_managed_artifact():
    home = pathlib.Path(tempfile.mkdtemp())
    source = home / "retired-style.md"
    target = home / ".claude" / "output-styles" / "retired-style.md"
    state = (
        home
        / ".claude"
        / ".mainframe-managed-artifacts"
        / "output-style-retired-style.md.json"
    )
    source.write_text("retired\n", encoding="utf-8")
    seeded = subprocess.run(
        [
            sys.executable,
            str(MANAGED_DELIVERY),
            "install",
            "--source",
            str(source),
            "--target",
            str(target),
            "--state",
            str(state),
            "--backup-root",
            str(home / "backups"),
        ],
        capture_output=True,
        text=True,
    )
    assert seeded.returncode == 0, seeded.stderr
    source.unlink()

    installed, _ = _run_installer("--claude", home=home)
    assert installed.returncode == 0, installed.stderr
    assert not target.exists()
    assert not state.exists()


def test_claude_dev_dry_run_is_adapter_scoped():
    proc, _ = _run_installer("--claude", "--dev", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "claude-code/{telemetry,feedback,model-lab}" in proc.stdout


def test_claude_dev_migrates_legacy_feedback_link():
    home = pathlib.Path(tempfile.mkdtemp())
    target = home / ".claude" / "skills" / "harness-feedback"
    target.parent.mkdir(parents=True)
    target.symlink_to(ROOT / "dev" / "skills" / "harness-feedback")

    installed, _ = _run_installer("--claude", "--dev", home=home)

    assert installed.returncode == 0, installed.stderr
    assert target.is_dir() and not target.is_symlink()
    assert (target / "SKILL.md").is_file()


def test_claude_dev_telemetry_settings_are_owned_and_reversible():
    installed, home = _run_installer("--claude", "--dev")
    assert installed.returncode == 0, installed.stderr
    settings = home / ".claude" / "settings.json"
    value = json.loads(settings.read_text(encoding="utf-8"))
    assert value["env"]["CLAUDE_CODE_ENABLE_TELEMETRY"] == "1"
    assert value["env"]["OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"] == "http/json"
    assert value["env"]["OTEL_LOG_USER_PROMPTS"] == "0"
    assert value["env"]["OTEL_LOG_TOOL_CONTENT"] == "0"

    value["env"]["USER_SETTING"] = "kept"
    settings.write_text(json.dumps(value), encoding="utf-8")
    reinstalled, _ = _run_installer("--claude", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr
    value = json.loads(settings.read_text(encoding="utf-8"))
    assert value["env"] == {
        "USER_SETTING": "kept",
    }


def test_plain_reinstall_disables_owned_dev_links():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    claude_dir = home / ".claude"
    data_link = claude_dir / "mainframe"
    feedback_link = claude_dir / "skills" / "harness-feedback"
    data_link.symlink_to(ROOT / "workspace" / "runtime")
    feedback_link.symlink_to(
        ROOT / "adapters" / "claude-code" / "dev" / "skills" / "harness-feedback"
    )

    reinstalled, _ = _run_installer("--claude", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr
    assert not data_link.exists() and not data_link.is_symlink()
    assert not feedback_link.exists() and not feedback_link.is_symlink()


def test_old_claude_stops_before_any_install_in_noninteractive_mode():
    proc, home = _run_installer("--claude", claude_version="2.1.100")
    assert proc.returncode != 0
    assert f"requires Claude Code {MIN_CLAUDE_VERSION}+" in proc.stdout
    assert "before making changes" in proc.stderr
    assert not (home / ".local" / "bin" / "secret").exists()
    assert not (home / ".claude").exists()


def test_missing_python_stops_before_shared_or_adapter_delivery():
    proc, home = _run_installer("--claude", broken_python=True)
    assert proc.returncode != 0
    assert "working python3 is required" in proc.stderr
    assert "no Claude adapter files were changed" in proc.stderr
    assert not (home / ".local" / "bin" / "secret").exists()
    assert not (home / ".claude").exists()


def test_yes_updates_old_claude_before_installing():
    proc, home = _run_installer(
        "--claude", "--yes", claude_version="2.1.100")
    assert proc.returncode == 0, proc.stderr
    assert (home / "claude-version").read_text() == MIN_CLAUDE_VERSION
    assert "Claude Code updated" in proc.stdout
    assert (home / ".local" / "bin" / "secret").is_symlink()


def test_old_claude_dry_run_reports_update_without_changing_version():
    proc, home = _run_installer(
        "--claude", "--dry-run", claude_version="2.1.100")
    assert proc.returncode == 0, proc.stderr
    assert "would ask to run 'claude update'" in proc.stdout
    assert (home / "claude-version").read_text() == "2.1.100"
    assert not (home / ".local" / "bin" / "secret").exists()


def test_claude_uninstall_preserves_shared_secrets():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    helper = home / ".local" / "bin" / "secret"
    assert helper.is_symlink()
    assert (home / ".claude" / "CLAUDE.md").is_file()
    assert not (home / ".claude" / "CLAUDE.md").is_symlink()
    index_link = home / ".claude" / "credentials-index.md"
    assert index_link.is_symlink()
    assert index_link.resolve() == SHARED_CREDENTIALS / "credentials-index.md"
    assert (home / ".claude" / "skills" / "mainframe").is_dir()
    assert not (home / ".claude" / "skills" / "mainframe").is_symlink()
    assert (home / ".claude" / "agents" / "mainframe").is_dir()
    assert not (home / ".claude" / "agents" / "mainframe").is_symlink()
    settings = home / ".claude" / "settings.json"
    settings_state = home / ".claude" / ".mainframe-settings-state.json"
    assert settings.is_file() and not settings.is_symlink()
    assert settings_state.is_file()
    assert stat.S_IMODE(settings.stat().st_mode) == 0o600
    assert stat.S_IMODE(settings_state.stat().st_mode) == 0o600

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert helper.is_symlink()
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not index_link.exists() and not index_link.is_symlink()
    assert not (home / ".claude" / "skills" / "mainframe").exists()
    assert not (home / ".claude" / "agents" / "mainframe").exists()
    assert not settings.exists()
    assert not settings_state.exists()


def test_clean_uninstall_creates_nothing_and_needs_no_python():
    proc, home = _run_installer("--claude", "--uninstall", broken_python=True)
    assert proc.returncode == 0, proc.stderr
    assert "Nothing to uninstall" in proc.stdout
    assert not (home / ".claude").exists()
    assert not (home / ".local" / "bin" / "secret").exists()


def test_installed_uninstall_fails_closed_without_python():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr

    removed, _ = _run_installer(
        "--claude", "--uninstall", home=home, broken_python=True
    )
    assert removed.returncode != 0
    assert "working python3 is required" in removed.stderr
    assert (home / ".claude" / "CLAUDE.md").is_file()
    assert not (home / ".claude" / "CLAUDE.md").is_symlink()
    assert (home / ".claude" / "skills" / "mainframe").is_dir()
    assert not (home / ".claude" / "skills" / "mainframe").is_symlink()
    assert (home / ".claude" / "agents" / "mainframe").is_dir()
    assert not (home / ".claude" / "agents" / "mainframe").is_symlink()


def test_settings_migrate_legacy_link_to_regular_user_file():
    home = pathlib.Path(tempfile.mkdtemp())
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.symlink_to(ADAPTER / "export" / "settings.json")

    installed, _ = _run_installer("--claude", home=home)
    assert installed.returncode == 0, installed.stderr
    assert settings.is_file() and not settings.is_symlink()
    migrated = json.loads(settings.read_text(encoding="utf-8"))
    assert "model" not in migrated
    assert "effortLevel" not in migrated
    assert list(claude_dir.glob("settings.json.backup-*"))


def test_settings_preserve_user_values_and_restore_managed_values():
    home = pathlib.Path(tempfile.mkdtemp())
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text(
        json.dumps({
            "model": "haiku",
            "custom": {"kept": True},
            "permissions": {
                "allow": ["Bash(git add *)", "Bash(custom *)"],
            },
            "enabledPlugins": {
                "context7@claude-plugins-official": False,
            },
        }),
        encoding="utf-8",
    )
    settings.chmod(0o640)

    installed, _ = _run_installer("--claude", home=home)
    assert installed.returncode == 0, installed.stderr
    merged = json.loads(settings.read_text(encoding="utf-8"))
    assert merged["model"] == "haiku"
    assert merged["custom"] == {"kept": True}
    assert merged["enabledPlugins"]["context7@claude-plugins-official"] is True
    assert merged["permissions"]["allow"].count("Bash(git add *)") == 1
    assert "Bash(custom *)" in merged["permissions"]["allow"]
    assert stat.S_IMODE(settings.stat().st_mode) == 0o640

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    restored = json.loads(settings.read_text(encoding="utf-8"))
    assert restored["model"] == "haiku"
    assert restored["custom"] == {"kept": True}
    assert restored["enabledPlugins"]["context7@claude-plugins-official"] is False
    assert restored["permissions"] == {
        "allow": ["Bash(git add *)", "Bash(custom *)"]
    }


def test_settings_release_a_user_changed_default_on_reinstall():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    settings = home / ".claude" / "settings.json"
    value = json.loads(settings.read_text(encoding="utf-8"))
    value["model"] = "haiku"
    settings.write_text(json.dumps(value), encoding="utf-8")

    reinstalled, _ = _run_installer("--claude", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr
    assert json.loads(settings.read_text(encoding="utf-8"))["model"] == "haiku"

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert json.loads(settings.read_text(encoding="utf-8")) == {"model": "haiku"}


def test_settings_reconcile_removed_owned_template_values():
    work = pathlib.Path(tempfile.mkdtemp())
    source = work / "source.json"
    target = work / "settings.json"
    state = work / "state.json"
    source.write_text(json.dumps({
        "model": "fable",
        "permissions": {
            "allow": ["Bash(old *)"], "ask": [], "deny": [],
            "defaultMode": "auto",
        },
        "enabledPlugins": {"context7@claude-plugins-official": True},
    }), encoding="utf-8")
    target.write_text('{"custom":true}\n', encoding="utf-8")
    first = _run_settings_manager(
        "install", source, target, state, work / "first.backup"
    )
    assert first.returncode == 0, first.stderr

    source.write_text(json.dumps({
        "permissions": {
            "allow": ["Bash(new *)"], "ask": [], "deny": [],
            "defaultMode": "auto",
        },
        "enabledPlugins": {"context7@claude-plugins-official": True},
    }), encoding="utf-8")
    second = _run_settings_manager(
        "install", source, target, state, work / "second.backup"
    )
    assert second.returncode == 0, second.stderr
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["permissions"]["allow"] == ["Bash(new *)"]
    assert "model" not in merged


def test_settings_remove_retired_owned_session_choices():
    work = pathlib.Path(tempfile.mkdtemp())
    source = work / "source.json"
    target = work / "settings.json"
    state = work / "state.json"
    initial_template = {
        "model": "fable",
        "effortLevel": "xhigh",
        "permissions": {
            "allow": [], "ask": [], "deny": [], "defaultMode": "auto",
        },
        "enabledPlugins": {"context7@claude-plugins-official": True},
    }
    source.write_text(json.dumps(initial_template), encoding="utf-8")
    target.write_text('{"custom":true}\n', encoding="utf-8")
    first = _run_settings_manager(
        "install", source, target, state, work / "first.backup"
    )
    assert first.returncode == 0, first.stderr

    initial_template.pop("model")
    initial_template.pop("effortLevel")
    source.write_text(json.dumps(initial_template), encoding="utf-8")
    second = _run_settings_manager(
        "install", source, target, state, work / "second.backup"
    )
    assert second.returncode == 0, second.stderr
    migrated = json.loads(target.read_text(encoding="utf-8"))
    assert migrated["custom"] is True
    assert "model" not in migrated
    assert "effortLevel" not in migrated

    user_value = dict(migrated, model="claude-opus-4-8", effortLevel="medium")
    target.write_text(json.dumps(user_value), encoding="utf-8")
    third = _run_settings_manager(
        "install", source, target, state, work / "third.backup"
    )
    assert third.returncode == 0, third.stderr
    assert json.loads(target.read_text(encoding="utf-8")) == user_value


def test_invalid_user_settings_stop_before_shared_delivery():
    home = pathlib.Path(tempfile.mkdtemp())
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("not json\n", encoding="utf-8")

    proc, _ = _run_installer("--claude", home=home)
    assert proc.returncode != 0
    assert "cannot read valid JSON" in proc.stderr
    assert not (home / ".local" / "bin" / "secret").exists()


def test_incompatible_user_settings_stop_during_preflight():
    home = pathlib.Path(tempfile.mkdtemp())
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    settings.write_text('{"permissions":"invalid"}\n', encoding="utf-8")

    proc, _ = _run_installer("--claude", home=home)
    assert proc.returncode != 0
    assert "permissions must be an object" in proc.stderr
    assert settings.read_text(encoding="utf-8") == '{"permissions":"invalid"}\n'
    assert not (home / ".local" / "bin" / "secret").exists()


def test_unrelated_settings_and_state_symlinks_are_rejected():
    for name in ("settings.json", ".mainframe-settings-state.json"):
        home = pathlib.Path(tempfile.mkdtemp())
        claude_dir = home / ".claude"
        claude_dir.mkdir()
        unrelated = home / "unrelated.json"
        unrelated.write_text("{}\n", encoding="utf-8")
        (claude_dir / name).symlink_to(unrelated)

        proc, _ = _run_installer("--claude", home=home)
        assert proc.returncode != 0
        assert "refusing" in proc.stderr
        assert (claude_dir / name).is_symlink()
        assert not (home / ".local" / "bin" / "secret").exists()


def test_missing_user_settings_does_not_leave_stale_ownership():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    settings = home / ".claude" / "settings.json"
    state = home / ".claude" / ".mainframe-settings-state.json"
    settings.unlink()

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert not settings.exists()
    assert not state.exists()

    reinstalled, _ = _run_installer("--claude", home=home)
    assert reinstalled.returncode == 0, reinstalled.stderr
    assert settings.is_file()
    reinstalled_settings = json.loads(settings.read_text(encoding="utf-8"))
    assert "model" not in reinstalled_settings
    assert "effortLevel" not in reinstalled_settings


def test_adapter_owns_claude_artifacts():
    assert (ADAPTER / "install.sh").is_file()
    assert (ADAPTER / "export" / "CLAUDE.md").is_file()
    assert (PLUGIN / ".claude-plugin" / "plugin.json").is_file()
    assert AGENTS.is_dir()
    assert not (PLUGIN / "agents").exists()
    assert not (ROOT / "export").exists()
    assert not (ROOT / "plugin-dist").exists()


def test_readme_stays_product_focused_without_volatile_inventory():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## What it adds" in readme
    assert "## Origin and evolution" in readme
    assert "### Skills —" not in readme
    assert "### Agents —" not in readme
    assert "### Hooks —" not in readme
    assert "`severity-calibration`" not in readme


def test_agents_use_user_scope_names_and_plugin_skill_ids():
    paths = sorted(AGENTS.glob("*.md"))
    assert len(paths) == 7
    names = []
    for path in paths:
        body = path.read_text(encoding="utf-8")
        match = re.search(r"^name: ([a-z0-9-]+)$", body, re.MULTILINE)
        assert match, path
        name = match.group(1)
        names.append(name)
        assert name == path.stem
        assert name.startswith("mainframe-")
        assert "adapters/claude-code/plugin/agents" not in body
        skills = re.search(r"^skills:\n((?:  - .+\n)+)", body, re.MULTILINE)
        if skills:
            for skill in re.findall(r"^  - (.+)$", skills.group(1), re.MULTILINE):
                assert skill.startswith("mainframe:"), (path, skill)
    assert len(names) == len(set(names))


def test_infrastructure_is_primary_session_skill_not_agent():
    assert not (AGENTS / "mainframe-devops-engineer.md").exists()
    skill = PLUGIN / "skills" / "infrastructure"
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "disable-model-invocation: true" not in body
    assert "<project-root>/.agents/infrastructure.json" in body
    assert "mainframe:secrets-handling" in body
    assert "../dokploy-api/SKILL.md" in body
    assert "only when repository edits are within the active task" in body
    assert "without changing repository files" in body
    map_contract = (skill / "infrastructure-map.md").read_text(encoding="utf-8")
    verification = (skill / "verification.md").read_text(encoding="utf-8")
    assert (
        "Repair the map only when repository edits are within the task" in map_contract
    )
    assert "return the exact required map" in verification
    assert "update without editing it" in verification
    example = json.loads(
        (skill / "infrastructure.example.json").read_text(encoding="utf-8")
    )
    assert example["schemaVersion"] == 1
    assert example["environments"]["production"]["credentialRefs"]

    infrastructure = (
        PLUGIN / "skills" / "infrastructure" / "SKILL.md"
    ).read_text(encoding="utf-8")
    infrastructure_map = (
        PLUGIN / "skills" / "infrastructure" / "infrastructure-map.md"
    ).read_text(encoding="utf-8")
    assert "do not ask again when it does" in infrastructure
    assert "absence from the list does not grant it" in infrastructure_map
    assert "every material fact" in infrastructure
    assert "every material fact" in infrastructure_map
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert '"matcher": "Skill"' in hooks
    assert "skill-authority.py" in hooks
    assert (PLUGIN / "hooks" / "scripts" / "skill-authority.py").is_file()


def test_dokploy_branch_is_version_aware_and_secret_safe():
    skill_dir = PLUGIN / "skills" / "dokploy-api"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    all_markdown = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(skill_dir.glob("*.md"))
    )
    normalized = " ".join(all_markdown.split())

    assert "disable-model-invocation: true" in skill
    assert "target instance" in skill
    assert "authority already supplied" in all_markdown
    assert "global permission pattern for `curl`" in normalized
    assert "project.remove" in all_markdown
    assert "postgres.remove" in all_markdown
    assert "settings.reloadTraefik" in all_markdown
    assert "must not be requested again" in normalized
    assert "docs.dokploy.com/docs/api" in skill
    assert "43 total" not in all_markdown
    assert "529" not in all_markdown
    assert "850 KB" not in all_markdown
    assert "manualBackupLibsql" not in all_markdown
    assert "H=(" not in all_markdown
    assert '${H[@]}' not in all_markdown
    assert "curl -sS" not in all_markdown
    assert "unsupported for remote servers" in all_markdown
    assert "not supported for Compose deployments" in all_markdown
    assert "secret get REGISTERED_DB_PASSWORD | jq" in all_markdown
    assert "secret get REGISTERED_STORAGE_SECRET | jq" in all_markdown


def test_test_auditor_is_non_implementing_and_ticket_scoped():
    auditor = (AGENTS / "mainframe-test-auditor.md").read_text(encoding="utf-8")
    assert "tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch," in auditor
    assert "current primary documentation" in auditor
    assert "mainframe:testing-strategy" in auditor
    assert "mainframe:ticket" in auditor
    assert 'matcher: "Edit|Write"' in auditor
    assert 'matcher: "Bash"' in auditor
    assert "test-auditor-write-guard.py" in auditor
    assert "Do not use for routine implementation" in auditor
    assert "inspect the exact command, lifecycle scripts" in auditor
    assert "Run a broad or expensive suite only when measuring that suite" in auditor
    assert "create only `docs/tickets/open/needs-scope-review/`" in auditor
    assert (AGENTS / "hooks" / "test-auditor-write-guard.py").is_file()


def test_only_implementation_agents_receive_project_local_memory():
    implementation_agents = {
        "mainframe-python-backend-engineer.md",
        "mainframe-typescript-backend-engineer.md",
        "mainframe-react-frontend-engineer.md",
    }
    for path in sorted(AGENTS.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        normalized = " ".join(body.split())
        if path.name in implementation_agents:
            assert re.search(r"^memory: local$", body, re.MULTILINE)
            assert "verified, durable facts that reduce future" in normalized
            assert "Never store secrets, guesses, transient task state" in normalized
        else:
            assert not re.search(r"^memory:", body, re.MULTILINE)


def test_testing_context_preserves_role_boundaries():
    strategy = (PLUGIN / "skills" / "testing-strategy" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized_strategy = " ".join(strategy.split())
    assert "An implementation owner may create, change, and run tests" in normalized_strategy
    assert "An audit-only recipient evaluates the existing evidence" in normalized_strategy
    assert "cross-cutting testing strategy" in normalized_strategy
    assert "Not for routine focused tests" in normalized_strategy
    assert "--maxWorkers=2 --no-file-parallelism" in strategy
    assert "Never use broad `pkill` or `killall`" in strategy

    profiles = {
        "mainframe-python-backend-engineer.md": "mainframe:python-backend-patterns",
        "mainframe-typescript-backend-engineer.md": "mainframe:typescript-backend-patterns",
        "mainframe-react-frontend-engineer.md": "mainframe:frontend",
    }
    for filename, profile_skill in profiles.items():
        body = (AGENTS / filename).read_text(encoding="utf-8")
        assert profile_skill in body
        assert "mainframe:testing-strategy" not in body

    python_agent = (AGENTS / "mainframe-python-backend-engineer.md").read_text(
        encoding="utf-8"
    )
    python_skill = (PLUGIN / "skills" / "python-backend-patterns" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "disable-model-invocation: true" not in python_skill
    assert "user-invocable: false" in python_skill
    assert "[testing.md](testing.md)" in python_skill
    for reference in (
        "auth-and-sessions.md",
        "background-and-realtime.md",
        "files-and-integrations.md",
    ):
        assert f"]({reference})" in python_skill
    assert "~/.claude" not in python_agent
    assert "senior enterprise" not in python_agent.lower()
    assert "does not mandate FastAPI" in python_skill
    assert "concrete adjacent observation" in python_agent
    assert "without investigating it" in python_agent
    assert "verified out-of-scope defects" not in python_skill
    assert "## Testing baseline" in python_skill
    assert "observe the focused test fail" in python_skill
    assert (
        "Inspect the exact command, task, configuration, and relevant fixtures"
        in python_skill
    )
    assert "do not prove" in python_skill
    assert "observe the focused test fail" not in python_agent
    assert "Complete the assigned behavior" in python_skill
    assert "deferred in-scope work as a substitute" in python_skill

    python_testing = (
        PLUGIN / "skills" / "python-backend-patterns" / "testing.md"
    ).read_text(encoding="utf-8")
    assert "existing test runner" in python_testing
    assert "do not introduce pytest" in python_testing
    for testing in (
        python_testing,
        (PLUGIN / "skills" / "typescript-backend-patterns" / "testing.md").read_text(
            encoding="utf-8"
        ),
        (PLUGIN / "skills" / "frontend" / "references" / "testing.md").read_text(
            encoding="utf-8"
        ),
    ):
        assert "never start" in testing.lower()
        assert "pkill" in testing and "killall" in testing

    python_sqlalchemy = (
        PLUGIN / "skills" / "python-backend-patterns" / "sqlalchemy.md"
    ).read_text(encoding="utf-8")
    assert "does not recommend combining" in python_sqlalchemy
    assert "not officially supported across backends" not in python_sqlalchemy

    typescript_skill = (
        PLUGIN / "skills" / "typescript-backend-patterns" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "disable-model-invocation: true" not in typescript_skill
    assert "[testing.md](testing.md)" in typescript_skill
    assert not (AGENTS / "mainframe-nestjs-backend-engineer.md").exists()
    assert not (AGENTS / "mainframe-nextjs-backend-engineer.md").exists()
    assert not (PLUGIN / "skills" / "nestjs-backend-patterns").exists()
    assert not (PLUGIN / "skills" / "nextjs-backend-patterns").exists()
    typescript_agent = (
        AGENTS / "mainframe-typescript-backend-engineer.md"
    ).read_text(encoding="utf-8")
    nextjs_reference = (
        PLUGIN / "skills" / "typescript-backend-patterns" / "nextjs-server.md"
    ).read_text(encoding="utf-8")
    assert "Next.js server code" in typescript_agent
    assert "Next.js App Router server code" not in typescript_agent
    assert "Pages API Routes" in typescript_skill
    assert "begin an App Router migration as incidental cleanup" in nextjs_reference
    assert "concrete adjacent observation" in typescript_agent
    assert "without investigating it" in typescript_agent
    assert "verified out-of-scope defects" not in typescript_skill
    assert "## Testing baseline" in typescript_skill
    assert "observe the focused test fail" in typescript_skill
    assert "observe the focused test fail" not in typescript_agent
    assert "Inspect the exact package script before running it" in typescript_skill
    assert "Complete the assigned behavior" in typescript_skill
    assert "deferred in-scope work as a substitute" in typescript_skill
    typescript_runtime = (
        PLUGIN / "skills" / "typescript-backend-patterns" / "runtime.md"
    ).read_text(encoding="utf-8")
    assert "the name is not a\n  safety contract" in typescript_runtime

    react_agent = (AGENTS / "mainframe-react-frontend-engineer.md").read_text(
        encoding="utf-8"
    )
    assert "React web applications and client React layers" in react_agent
    assert "React web work in Vite applications" not in react_agent
    assert "Bash, WebSearch" in react_agent
    assert "Skill" not in re.search(
        r"^tools: (.+)$", react_agent, re.MULTILINE
    ).group(1).split(", ")
    assert "TodoWrite" not in react_agent
    react_preloads = re.search(
        r"^skills:\n((?:  - .+\n)+)", react_agent, re.MULTILINE
    ).group(1)
    for expected in (
        "mainframe:frontend",
        "mainframe:ticket",
    ):
        assert expected in react_preloads
    for removed in ("react-frontend-patterns", "shadcn", "frontend-design"):
        assert not (PLUGIN / "skills" / removed).exists()
    react_skill = (PLUGIN / "skills" / "frontend" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "disable-model-invocation: true" not in react_skill
    assert "[testing](references/testing.md)" in react_skill
    assert "does not mandate FSD" in react_skill
    assert "concrete adjacent observation" in react_agent
    assert "without investigating it" in react_agent
    assert "verified out-of-scope defects" not in react_skill
    assert "## Testing baseline" in react_skill
    assert "observe the focused test fail" in react_skill
    assert "Inspect the exact package script, lifecycle scripts" in react_skill
    assert "observe the focused test fail" not in react_agent
    assert "Complete the assigned behavior" in react_skill
    assert "deferred in-scope work as a substitute" in react_skill

    for route in (
        "references/mode-operate.md",
        "references/mode-persuade.md",
        "references/mode-read.md",
        "references/mode-experience.md",
    ):
        assert route in react_skill
    assert "references/flows-and-feedback.md" in react_skill
    assert "scripts/inspect-ui.mjs" in react_skill
    assert '"shadcn": false' in react_skill

    observation = (
        PLUGIN / "skills" / "ticket" / "record-observation.md"
    ).read_text(encoding="utf-8")
    ticket = (PLUGIN / "skills" / "ticket" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "assigned result or agreed definition of done" in ticket
    assert "initial confirmation" in ticket
    normalized_observation = " ".join(observation.split())
    assert "active task's assigned result" in normalized_observation
    assert "broad discovery run" in normalized_observation
    assert "most distinctive available" in observation
    assert "two or three terms" not in observation


def test_researcher_has_private_methodology_boundary():
    researcher = (AGENTS / "mainframe-researcher.md").read_text(encoding="utf-8")
    assert "bounded external-research block" in researcher
    assert "technical mainframe-researcher" not in researcher
    assert "## Method" not in researcher and "## Return" not in researcher
    assert "Follow that method's boundary, evidence, stopping, and" in researcher
    assert "tools: Read, WebSearch, WebFetch," in researcher
    assert "Grep" not in researcher and "Glob" not in researcher and "Bash" not in researcher
    assert "skills:" not in researcher
    assert 'matcher: "Read"' in researcher
    assert 'matcher: "WebSearch|' in researcher
    assert "mcp__plugin_context7_context7__resolve-library-id" in researcher
    assert "mcp__plugin_context7_context7__query-docs" in researcher
    assert 'matcher: "WebFetch"' in researcher
    assert "research-read-guard.py" in researcher
    assert "skills/mainframe/skills/research-method/SKILL.md" in researcher

    method = PLUGIN / "skills" / "research-method"
    body = (method / "SKILL.md").read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in body
    assert "user-invocable: false" in body
    assert "this common method and at least one profile" in body
    assert "Fetch it again only when" in body
    assert "Re-open each load-bearing source" not in body
    for guide in ("software-documentation.md", "economics.md", "news.md"):
        assert (method / "references" / guide).is_file()


def test_decision_reviewer_reads_private_method_without_false_preload():
    reviewer = (AGENTS / "mainframe-decision-reviewer.md").read_text(
        encoding="utf-8"
    )
    assert "model: opus" in reviewer
    assert "effort: medium" in reviewer
    assert "mainframe:severity-calibration" not in reviewer
    assert "mainframe:decision-review" not in reviewer
    assert "skills/mainframe/skills/decision-review/SKILL.md" in reviewer
    assert "CLAUDE.md" not in reviewer
    assert "Cap source lookups" not in reviewer
    assert "<!--" not in reviewer
    assert "permissionMode: plan" not in reviewer
    assert "Write" not in reviewer.split("---", 2)[1]
    assert "Edit" not in reviewer.split("---", 2)[1]
    assert "Bash" not in reviewer.split("---", 2)[1]

    method = (PLUGIN / "skills" / "decision-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "disable-model-invocation: true" in method
    assert "user-invocable: false" in method
    assert "Triggered via agent frontmatter `skills:` preload" not in method
    assert "Preloaded into" not in method
    assert "Critical" in method and "High" in method
    assert "dialectical inquiry outperforms" not in method
    assert "10.1002/smj.4250010403" not in method
    assert "six months later" not in method
    assert "realistic failure horizon" in method
    assert "Add an independent check only when" in method
    assert "anthropic.com/news/towards-understanding-sycophancy" in method
    assert "unverifiable" in reviewer and "unverifiable" in method
    assert not (PLUGIN / "skills" / "severity-calibration").exists()

    workflow = (PLUGIN / "skills" / "init" / "workflow.md").read_text(
        encoding="utf-8"
    )
    assert "Give `mainframe-decision-reviewer` the prepared facts" in workflow
    assert "conversation context that the subagent does not receive" in workflow


def test_advisor_is_controlled_read_only_and_replaces_builtin_advisor():
    advisor = (AGENTS / "mainframe-advisor.md").read_text(encoding="utf-8")
    assert "tools: Read, Grep, Glob, WebSearch, WebFetch," in advisor
    assert "Bash" not in advisor and "Write" not in advisor and "Edit" not in advisor
    assert "model: opus" in advisor
    assert "effort: high" in advisor
    assert "background: true" in advisor
    assert "permissionMode: plan" not in advisor
    assert "MAINFRAME_ADVISOR_CONTEXT_V1" in advisor
    assert "VERDICT: UNVERIFIABLE" in advisor
    assert "Add an independent check only" in advisor

    workflow = (PLUGIN / "skills" / "init" / "workflow.md").read_text(
        encoding="utf-8"
    )
    settings = json.loads((ADAPTER / "export" / "settings.json").read_text())
    assert "mainframe-advisor" in workflow
    assert "zero-argument" not in workflow
    assert "built-in" not in workflow
    assert "advisorModel" not in settings


def test_old_general_code_audit_and_shared_severity_skill_are_not_delivered():
    assert not (PLUGIN / "skills" / "code-audit").exists()
    assert not (PLUGIN / "skills" / "severity-calibration").exists()


def test_marker_quality_is_enforced_by_hooks_not_a_discovery_skill():
    assert not (PLUGIN / "skills" / "no-suppression-markers").exists()
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    post = json.dumps(hooks["hooks"]["PostToolUse"])
    stop = json.dumps(hooks["hooks"]["Stop"])
    subagent_stop = json.dumps(hooks["hooks"]["SubagentStop"])
    assert "scan-suppression-markers.py" in post
    assert "stop-gate-suppression-markers.py" in stop
    assert "stop-gate-suppression-markers.py" in subagent_stop


def test_dev_permission_audit_observes_requests_without_deciding_them():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    permission = json.dumps(hooks["hooks"]["PermissionRequest"])
    assert '"matcher": "*"' in permission
    assert "run-telemetry-hook.sh" in permission
    assert "telemetry.py" in permission
    assert (PLUGIN / "hooks" / "scripts" / "_permission_audit.py").is_file()


def test_server_safety_does_not_grant_or_assume_destructive_bash():
    body = (PLUGIN / "skills" / "ops-app-server-safety" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "allowed-tools: Bash" not in body
    assert "docker compose up --no-recreate" not in body
    assert "Do not force-kill by default" in body
    assert "Use `docker compose down` only" in body
    assert "launch it without an extra confirmation round" in body
    assert "Do not silently turn a restart into a fresh start" in body
    assert "ps --status running --services" in body
    assert "default table output is not a valid emptiness check" in body
    assert "A live PID or container alone proves only" in body


def test_secrets_skill_uses_index_without_secret_ownership_drift():
    body = (PLUGIN / "skills" / "secrets-handling" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(body.split())
    assert "~/.claude/credentials-index.md" in normalized
    assert "Never read" in normalized
    assert "Return the exact missing credential" in normalized
    assert "Ask the user" not in normalized
    assert "migrate first" not in normalized
    assert "Regex (PCRE)" not in normalized


def test_curl_skill_preserves_http_and_authority_boundaries():
    body = (PLUGIN / "skills" / "curl-requests" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(body.split())
    assert "400 or greater" in normalized
    assert "do not treat 3xx as failure" in normalized
    assert "does not authorize POST" in normalized
    assert "Put `--disable` first" in normalized
    assert "curl --disable -sS" in body
    assert "it repeats other custom headers there" in normalized
    assert "--location-trusted" in normalized
    assert "Show the command before executing" not in normalized
    assert "Do not add `-X POST`" in normalized


def test_umbrella_has_no_delivery_metadata_comment():
    umbrella = (ADAPTER / "export" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Source of truth:" not in umbrella
    assert "This file is symlinked" not in umbrella


def test_umbrella_is_role_agnostic():
    umbrella = (ADAPTER / "export" / "CLAUDE.md").read_text(encoding="utf-8")
    forbidden_sections = (
        "Partnership",
        "Communication",
        "Engineering practices",
        "Problem-solving",
        "Orchestration",
        "Memory",
        "Advisor",
        "Git and commits",
    )
    for section in forbidden_sections:
        assert not re.search(rf"^#+ {re.escape(section)}$", umbrella, re.MULTILINE)
    assert "regardless of role" not in umbrella
    assert "immediate caller" in umbrella
    assert "Do not take ownership" not in umbrella
    assert "user communication" not in umbrella
    assert "authoritative sources" in umbrella
    assert "secret" in umbrella
    assert "supporting evidence to your immediate caller" not in umbrella
    assert "Return enough evidence for the caller" not in umbrella
    assert "externally mutating" in umbrella
    assert "irreversible, external, or out-of-scope" not in umbrella
    normalized = " ".join(umbrella.split())
    assert "accurate unfavorable finding" in normalized
    assert "Before a consequential action" in normalized
    assert "smallest adequate check" in normalized
    assert "narrow green check" in normalized
    assert "TODOs" not in umbrella
    assert "plain language" not in umbrella


def test_init_skill_is_manual_only():
    skill = PLUGIN / "skills" / "init" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "name: init" in body
    assert "disable-model-invocation: true" in body
    assert "context: fork" not in body
    normalized = " ".join(body.split())
    assert "technical detail into practical consequences" in normalized
    assert "safest practical path" in normalized
    assert "When implementing directly" in normalized
    assert "deferred in-scope work as a substitute" in normalized


def test_ticket_run_skills_prepare_native_goals_in_primary_session():
    expected = {
        "tickets-find": "open/observations",
        "tickets-refine": "open/needs-scope-review",
        "tickets-implement": "open/ready",
        "tickets-verify": "open/needs-verification",
    }
    for name, queue in expected.items():
        body = (PLUGIN / "skills" / name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert f"name: {name}" in body
        assert 'argument-hint: "[scope]"' in body
        assert "disable-model-invocation: true" in body
        assert "context: fork" not in body
        assert "$ARGUMENTS" in body
        assert "/goal Follow the loaded" in body
        assert queue in body
        assert "Do not start" in body
        assert "user asks to pause or cancel" in body

    shared = (
        PLUGIN / "references" / "ticket-autonomous-runs.md"
    ).read_text(encoding="utf-8")
    assert "current local checkout" in shared
    assert "Do not create or switch branches or worktrees" in shared
    assert "do not ask the user to resolve technical choices" in shared.lower()
    assert "explicit enough for the `/goal` evaluator" in shared

    refinement = (
        PLUGIN / "skills" / "tickets-refine" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "semantic duplicates" in refinement
    assert "Do not run tests" in refinement
    assert "execution: autonomous" in refinement

    discovery = (
        PLUGIN / "skills" / "tickets-find" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "normalize current open tickets" in discovery
    assert "`NOT COVERED`" in discovery
    assert "unexamined coverage" in discovery

    implementation = (
        PLUGIN / "skills" / "tickets-implement" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "execution: autonomous" in implementation
    assert "execution: user-approved" in implementation
    assert "Missing or stale eligibility" in implementation

    verification = (
        PLUGIN / "skills" / "tickets-verify" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "fresh session" in verification
    assert "do not repair code inline" in verification.lower()
    assert "existing execution route" in " ".join(verification.split())

    ticket_format = (
        PLUGIN / "skills" / "ticket" / "ticket-format.md"
    ).read_text(encoding="utf-8")
    assert "Normalize legacy open tickets during discovery" in ticket_format
    assert "execution: autonomous" in ticket_format
    assert "execution: user-approved" in ticket_format
    assert "idempotent" in ticket_format


def test_init_ticket_route_handles_one_user_decision_before_goal():
    init_dir = PLUGIN / "skills" / "init"
    body = (init_dir / "SKILL.md").read_text(encoding="utf-8")
    route = (init_dir / "ticket-decision.md").read_text(encoding="utf-8")
    assert 'argument-hint: "[ticket <id>]"' in body
    assert "[ticket-decision.md](ticket-decision.md)" in body
    assert "exactly one" in body
    assert "one ticket" in route
    normalized_route = " ".join(route.split())
    assert "before asking the user" in normalized_route
    assert "Agree a concise definition of done" in route
    assert "obtain focused red evidence before" in route
    assert "Do not start implementation before the user sends the goal" in route
    assert "/goal Implement only ticket <id>" in route
    assert "open/needs-verification" in route
    assert "execution: user-approved" in route


def test_init_replaces_automatic_task_workflow():
    init_dir = PLUGIN / "skills" / "init"
    body = (init_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "[workflow.md](workflow.md)" in body
    assert "mainframe-peer-review" in body
    assert (init_dir / "workflow.md").is_file()
    assert not (init_dir / "codex-exec.md").exists()
    assert (ADAPTER / "optional" / "skills" / "mainframe-peer-review" / "SKILL.md").is_file()
    assert not (PLUGIN / "skills" / "task-workflow").exists()
    assert not (PLUGIN / "hooks" / "scripts" / "session-posture.py").exists()
    assert not (PLUGIN / "hooks" / "scripts" / "task-workflow-engagement.py").exists()
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "task-workflow" not in hooks
    assert "session-posture" not in hooks


def test_init_separates_bounded_dod_from_complex_review():
    init_dir = PLUGIN / "skills" / "init"
    workflow = (init_dir / "workflow.md").read_text(encoding="utf-8")
    codex = (
        ADAPTER / "optional" / "skills" / "mainframe-peer-review" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "A formal DoD alone does not make a task complex" in workflow
    assert "### Bounded formal route" in workflow
    assert "### Complex route" in workflow
    assert "without invoking `mainframe-decision-reviewer`," in workflow
    assert "These checkpoints are required for the complex route" in workflow
    assert "The bounded route ends after direct proof" in " ".join(workflow.split())
    assert "bounded formal" not in codex
    assert "gpt-5.6-terra" not in codex
    assert "`gpt-5.6-sol` with `medium`" in codex
    assert "Use `xhigh` only" in codex


def test_codex_review_isolated_from_user_configuration():
    codex = (
        ADAPTER / "optional" / "skills" / "mainframe-peer-review" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert codex.count("--ignore-user-config") == 2
    assert codex.count("--strict-config") == 2
    assert "--ignore-rules" not in codex
    assert "-s read-only" in codex
    assert "sandbox_mode=\"read-only\"" in codex


def test_workflow_preserves_only_non_reproducible_acceptance_evidence():
    workflow = (
        PLUGIN / "skills" / "init" / "workflow.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(workflow.split())
    assert "Prove the DoD from the final state" in normalized
    assert "acceptance depends on it or it cannot be reproduced later" in normalized
    assert "do not create process artifacts by default" in normalized
    assert "Make the result and evidence durable" not in workflow


def test_init_uses_one_user_decision_boundary():
    init_dir = PLUGIN / "skills" / "init"
    body = (init_dir / "SKILL.md").read_text(encoding="utf-8")
    workflow = (init_dir / "workflow.md").read_text(encoding="utf-8")
    for text in (body, workflow):
        normalized = " ".join(text.split())
        assert "product or business-logic" in normalized
        assert "material infrastructure choice" in normalized


def test_init_memory_saves_new_learnings_without_compaction_reread():
    body = (
        PLUGIN / "skills" / "init" / "SKILL.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(body.split())
    assert "save durable new learnings that are not already recorded" in normalized
    assert "Review memory" not in body
    assert "before older context is compacted" not in normalized


def test_init_does_not_infer_external_action_authority_from_goal():
    init_dir = PLUGIN / "skills" / "init"
    body = " ".join((init_dir / "SKILL.md").read_text(encoding="utf-8").split())
    workflow = " ".join(
        (init_dir / "workflow.md").read_text(encoding="utf-8").split()
    )
    for text in (body, workflow):
        assert "destructive, irreversible, or externally mutating" in text
    assert "grants only the action authority the user explicitly stated" in body
    assert "authority already supplied" in body
    assert "authorize implementation, not destructive, irreversible" in workflow
    assert "the user did not explicitly include" in workflow


def test_init_allows_only_ordinary_new_local_commits_without_request():
    init_dir = PLUGIN / "skills" / "init"
    body = " ".join((init_dir / "SKILL.md").read_text(encoding="utf-8").split())
    workflow = " ".join(
        (init_dir / "workflow.md").read_text(encoding="utf-8").split()
    )
    assert "ordinary new local commits on the branch present at session start" in body
    assert "`commit --amend`" in body
    assert "authorizes no other branch, history, worktree, or remote operation" in body
    assert "ordinary new local recovery commits" in workflow
    assert "any other history operation without explicit instruction" in workflow


def test_shared_secrets_have_one_runtime_index():
    assert (SHARED_CREDENTIALS / "install.sh").is_file()
    assert (SHARED_CREDENTIALS / "secret").is_file()
    assert (SHARED_CREDENTIALS / "credentials-index.template.md").is_file()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "shared/credentials/credentials-index.md"],
        cwd=ROOT,
    )
    assert ignored.returncode == 0
    installer = ADAPTER_INSTALLER.read_text(encoding="utf-8")
    assert (
        '"shared/credentials/credentials-index.md:'
        '${CLAUDE_DIR}/credentials-index.md"'
    ) in installer


def test_claude_permissions_expose_only_helper_and_index():
    settings = json.loads((ADAPTER / "export" / "settings.json").read_text())
    assert "minimumVersion" not in settings
    allowed = settings["permissions"]["allow"]
    denied = settings["permissions"]["deny"]
    assert "Bash(secret get *)" in allowed
    assert "Bash(secret *)" not in allowed
    for rule in (
        "Bash(secret set *)",
        "Bash(secret del *)",
        "Bash(secret edit *)",
        "Bash(secret list *)",
    ):
        assert rule in denied
    assert "Bash(secret edit)" not in denied
    assert "Bash(secret list)" not in denied
    assert "Read(~/.claude/credentials-index.md)" in allowed
    assert "Read(~/.config/credentials/**)" in denied
    assert "Read(**/secrets/**)" in denied
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "secret-read-guard.py" in hooks
    assert (PLUGIN / "hooks" / "scripts" / "secret-read-guard.py").is_file()


def test_global_settings_preserve_role_language_and_session_choice_contracts():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings["outputStyle"] == "Plain and Concise"
    assert "model" not in settings
    assert "effortLevel" not in settings
    assert "language" not in settings
    assert "preferredNotifChannel" not in settings
    assert "editorMode" not in settings
    assert "verbose" not in settings
    assert "remoteControlAtStartup" not in settings
    assert "skipWorkflowUsageWarning" not in settings
    assert "autoCompactEnabled" not in settings
    assert "frontend-design@claude-plugins-official" not in settings["enabledPlugins"]
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in settings.get("env", {})
    assert "teammateMode" not in settings


def test_global_settings_leave_native_autocompact_policy_to_claude_code():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    assert "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" not in settings["env"]
    assert "CLAUDE_CODE_AUTO_COMPACT_WINDOW" not in settings["env"]


def test_general_purpose_agent_is_denied_without_blocking_specialists():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    denied = settings["permissions"]["deny"]
    assert "Agent(general-purpose)" in denied
    assert "Agent(Explore)" not in denied
    assert "Agent(Plan)" not in denied
    assert not any("mainframe-" in rule for rule in denied)

    init = " ".join((
        PLUGIN / "skills" / "init" / "SKILL.md"
    ).read_text(encoding="utf-8").split())
    assert "If no specialist matches, work directly" in init
    assert "built-in general-purpose agent" in init
    assert "choose its model explicitly at invocation" in init
    assert "does not expose an effort override" in init
    assert "Do not use a catch-all built-in" in init


def test_output_style_is_plain_without_mandatory_teaching_blocks():
    styles = sorted((ADAPTER / "export" / "output-styles").glob("*.md"))
    assert [path.name for path in styles] == ["plain-and-concise.md"]
    body = styles[0].read_text(encoding="utf-8")
    assert "name: Plain and Concise" in body
    assert "keep-coding-instructions: true" in body
    assert "immediate reader" in body
    assert "Clarity and brevity must not hide material meaning" in body
    assert "★ Insight" not in body
    assert "before and after writing code" not in body


def test_sensitive_git_actions_require_runtime_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    allowed = settings["permissions"]["allow"]
    asked = settings["permissions"]["ask"]
    assert "Agent(isolation:*)" in asked
    assert "Bash(git add *)" in allowed
    assert "Bash(git commit *)" in allowed
    for command in (
        "git push", "git checkout", "git switch", "git pull",
        "git merge", "git rebase", "git reset", "git cherry-pick",
        "git revert", "git restore",
    ):
        rule = f"Bash({command} *)"
        assert rule in asked
        assert rule not in allowed
    assert "Bash(git commit *--amend*)" in asked
    assert "Bash(git stash *)" not in asked
    assert not any("git branch" in rule for rule in asked)
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "git-authority.py" in hooks
    assert '"if": "Bash(git *)"' in hooks
    assert '"if": "Bash(*/*git *)"' in hooks
    assert (PLUGIN / "hooks" / "scripts" / "git-authority.py").is_file()


def test_arbitrary_execution_and_network_do_not_bypass_auto_mode_checks():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    allowed = settings["permissions"]["allow"]
    for rule in (
        "Bash(npx *)", "Bash(python *)", "Bash(python3 *)", "Bash(node *)",
        "Bash(curl *)", "Bash(wget *)", "Bash(env *)", "Bash(source *)",
        "Bash(. *)", "Bash(direnv *)", "Bash(bash /tmp/*)",
        "Bash(sh /tmp/*)", "Bash(zsh /tmp/*)", "Bash(docker run *)",
        "Bash(docker compose up *)", "Bash(docker compose down *)",
        "Bash(docker compose restart *)",
    ):
        assert rule not in allowed

    bash_rules = {rule for rule in allowed if rule.startswith("Bash(")}
    assert bash_rules == {
        "Bash(secret get *)",
        "Bash(git add *)",
        "Bash(git commit *)",
        "Bash(git fetch *)",
    }


def test_recursive_delete_policy_defers_to_claude_native_permission_mode():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    assert "Bash(rm -rf *)" not in settings["permissions"]["ask"]
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "path-validation.py" not in hooks


def test_language_dependencies_use_auto_mode_not_manual_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]
    for rule in (
        "Bash(npm install *)", "Bash(npm i *)", "Bash(yarn add *)",
        "Bash(pnpm add *)", "Bash(pnpm install *)", "Bash(pip install *)",
        "Bash(pip3 install *)", "Bash(cargo install *)",
        "Bash(gem install *)", "Bash(go install *)",
    ):
        assert rule not in asked
    assert "Bash(brew install *)" in asked
    assert "Bash(apt install *)" in asked


def test_external_package_and_image_publications_require_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]
    for rule in (
        "Bash(npm publish *)", "Bash(pnpm publish *)",
        "Bash(yarn publish *)", "Bash(yarn npm publish *)",
        "Bash(twine upload *)", "Bash(python -m twine upload *)",
        "Bash(python3 -m twine upload *)", "Bash(uv publish *)",
        "Bash(poetry publish *)", "Bash(hatch publish *)",
        "Bash(cargo publish *)", "Bash(gem push *)",
        "Bash(docker push *)", "Bash(docker image push *)",
        "Bash(docker manifest push *)", "Bash(container image push *)",
        "Bash(container i push *)",
    ):
        assert rule in asked
    assert "Bash(pip upload *)" not in asked


def test_system_and_destructive_runtime_changes_keep_narrow_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]
    for rule in (
        "Bash(brew install *)", "Bash(apt install *)",
        "Bash(apt-get install *)", "Bash(chmod 777 *)",
        "Bash(chown *)", "Bash(sudo *)", "Bash(docker volume rm *)",
        "Bash(docker compose down -v*)", "Bash(docker system prune *)",
        "Bash(docker run *--privileged*)",
    ):
        assert rule in asked

    # Broad prompts cannot distinguish local diagnostics from an external or
    # material mutation. Auto mode and the caller's authority own that context.
    for rule in (
        "Bash(curl *)", "Bash(wget *)", "Bash(docker *)",
        "Bash(docker compose down *)", "Bash(npm install *)",
        "Bash(pip install *)", "Bash(docker rm *)", "Bash(docker rmi *)",
    ):
        assert rule not in asked


def test_apple_container_prompts_only_at_data_machine_and_external_boundaries():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]

    for rule in (
        "Bash(container volume delete *)",
        "Bash(container volume rm *)",
        "Bash(container volume prune*)",
        "Bash(container v delete *)",
        "Bash(container v rm *)",
        "Bash(container v prune*)",
        "Bash(container machine delete *)",
        "Bash(container machine rm *)",
        "Bash(container m delete *)",
        "Bash(container m rm *)",
        "Bash(/usr/local/bin/uninstall-container.sh -d*)",
        "Bash(uninstall-container.sh -d*)",
    ):
        assert rule in asked

    for rule in (
        "Bash(container delete *)",
        "Bash(container rm *)",
        "Bash(container prune*)",
        "Bash(container image delete *)",
        "Bash(container image rm *)",
        "Bash(container image prune*)",
        "Bash(container system stop*)",
    ):
        assert rule not in asked

    containers = (
        PLUGIN / "skills" / "infrastructure" / "containers.md"
    ).read_text(encoding="utf-8")
    assert "Apple's `container`" in containers
    assert "does not itself delete user data" in containers


def test_verified_local_postgres_is_disposable_without_manual_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]
    for rule in (
        "Bash(*DROP DATABASE*)",
        "Bash(*DROP SCHEMA*)",
        "Bash(*TRUNCATE TABLE*)",
    ):
        assert rule not in asked

    instructions = (ADAPTER / "export" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "verified to run entirely on this machine" in instructions
    assert "without separate approval" in instructions
    assert "tunnel, proxy, or remote endpoint" in instructions
    assert "remote, shared, staging, or production endpoint" in instructions


def test_http_permissions_prompt_only_for_direct_system_path_writes():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    asked = settings["permissions"]["ask"]

    for rule in (
        "Bash(curl *> ~/*)",
        "Bash(curl *-o ~/*)",
        "Bash(wget *-O ~/*)",
        "Bash(curl *-X DELETE*)",
    ):
        assert rule not in asked

    for rule in (
        "Bash(curl *> /etc/*)",
        "Bash(curl *> /usr/*)",
        "Bash(curl *-o /etc/*)",
        "Bash(curl *-o /usr/*)",
        "Bash(wget *-O /etc/*)",
        "Bash(wget *-O /usr/*)",
    ):
        assert rule in asked


def test_emergency_system_denies_match_commands_not_harmless_mentions():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    denied = settings["permissions"]["deny"]

    for stale_rule in (
        "Bash(*mkfs*)", "Bash(*dd if=*)", "Bash(*fdisk*)",
        "Bash(kill -9 1*)", "Bash(pkill -9 -1*)",
        "Bash(*chmod -R 777*)", "Bash(*chmod 777 /*)",
        "Bash(*chmod -R 000*)", "Bash(*chown -R root*)",
    ):
        assert stale_rule not in denied

    for rule in (
        "Bash(mkfs *)", "Bash(mkfs.* *)", "Bash(/sbin/mkfs *)",
        "Bash(/usr/sbin/mkfs *)", "Bash(dd *if=*)",
        "Bash(/bin/dd *if=*)", "Bash(/usr/bin/dd *if=*)",
        "Bash(fdisk *)", "Bash(/sbin/fdisk *)",
        "Bash(/usr/sbin/fdisk *)", "Bash(kill -9 1)",
        "Bash(kill -9 1 *)", "Bash(kill -9 -1)",
        "Bash(kill -9 -1 *)", "Bash(chmod -R 777 *)",
        "Bash(chmod 777 /*)", "Bash(chmod -R 000 *)",
        "Bash(chown -R root*)",
    ):
        assert rule in denied

    asked = settings["permissions"]["ask"]
    for stale_rule in ("Bash(*chmod 777*)", "Bash(*chown *)"):
        assert stale_rule not in asked
    for rule in (
        "Bash(chmod 777 *)", "Bash(/bin/chmod 777 *)",
        "Bash(chown *)", "Bash(/usr/sbin/chown *)",
    ):
        assert rule in asked


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
