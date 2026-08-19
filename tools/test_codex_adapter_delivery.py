#!/usr/bin/env python3
"""Contract tests for the first native Codex adapter baseline."""

import json
import hashlib
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
MANAGED_DELIVERY = ROOT / "shared" / "managed-delivery" / "manage-artifact.py"


def _agent_template_data(name, *, home):
    body = (ADAPTER / "agents" / f"{name}.toml.template").read_text(
        encoding="utf-8"
    )
    replacements = {
        "__MAINFRAME_RESEARCH_METHOD_SKILL__": home
        / ".codex"
        / "mainframe"
        / "private-skills"
        / "mainframe-research-method"
        / "SKILL.md",
        "__MAINFRAME_DECISION_REVIEW_SKILL__": home
        / ".codex"
        / "mainframe"
        / "private-skills"
        / "mainframe-decision-review"
        / "SKILL.md",
        "__MAINFRAME_READINESS_REVIEW_SKILL__": home
        / ".codex"
        / "mainframe"
        / "private-skills"
        / "mainframe-readiness-review"
        / "SKILL.md",
        "__MAINFRAME_PYTHON_BACKEND_SKILL__": home
        / ".agents"
        / "skills"
        / "mainframe-python-backend"
        / "SKILL.md",
        "__MAINFRAME_TYPESCRIPT_BACKEND_SKILL__": home
        / ".agents"
        / "skills"
        / "mainframe-typescript-backend"
        / "SKILL.md",
        "__MAINFRAME_FRONTEND_SKILL__": home
        / ".agents"
        / "skills"
        / "mainframe-frontend"
        / "SKILL.md",
        "__MAINFRAME_TESTING_STRATEGY_SKILL__": home
        / ".agents"
        / "skills"
        / "mainframe-testing-strategy"
        / "SKILL.md",
        "__MAINFRAME_TICKET_SKILL__": home
        / ".agents"
        / "skills"
        / "mainframe-ticket"
        / "SKILL.md",
    }
    for marker, path in replacements.items():
        body = body.replace(marker, str(path.resolve()))
    assert "__MAINFRAME_" not in body
    return tomllib.loads(body)


def _write_fake_codex(
    path, *, hooks_supported=True, feature_rows=0,
    require_existing_codex_home=False,
):
    hooks_value = "true" if hooks_supported else "false"
    path.write_text(
        "#!/bin/sh\n"
        + (
            "if [ ! -d \"${CODEX_HOME:-$HOME/.codex}\" ]; then exit 42; fi\n"
            if require_existing_codex_home
            else ""
        )
        +
        "if [ \"${1:-}\" = --version ]; then echo 'codex-cli 0.147.0'; exit 0; fi\n"
        "if [ \"${1:-}\" = features ] && [ \"${2:-}\" = list ]; then\n"
        "  awk 'BEGIN {\n"
        f"    print \"hooks stable {hooks_value}\";\n"
        f"    for (i = 0; i < {feature_rows}; i++) print \"feature_\" i \" stable false\";\n"
        "  }'\n"
        "  exit $?\n"
        "fi\n"
        "if [ \"${1:-}\" = execpolicy ] && [ \"${2:-}\" = check ]; then "
        "echo '{\"decision\":\"prompt\"}'; exit 0; fi\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run(
    *args,
    home=None,
    desktop_hooks_supported=True,
    feature_rows=0,
    require_existing_codex_home=False,
    claude_peer=False,
):
    home = home or pathlib.Path(tempfile.mkdtemp())
    fake_bin = home / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    codex = fake_bin / "codex"
    desktop_codex = fake_bin / "codex-desktop"
    _write_fake_codex(
        codex,
        feature_rows=feature_rows,
        require_existing_codex_home=require_existing_codex_home,
    )
    _write_fake_codex(
        desktop_codex,
        hooks_supported=desktop_hooks_supported,
        feature_rows=feature_rows,
        require_existing_codex_home=require_existing_codex_home,
    )
    if claude_peer:
        claude = fake_bin / "claude"
        claude.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = auth ] && [ \"${2:-}\" = status ]; then exit 0; fi\n"
            "if [ \"${1:-}\" = --version ]; then echo '2.1.226 (Claude Code)'; exit 0; fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        claude.chmod(claude.stat().st_mode | stat.S_IXUSR)
    env = dict(
        os.environ,
        HOME=str(home),
        PATH=f"{fake_bin}:/usr/bin:/bin",
        MAINFRAME_CODEX_DESKTOP_RUNTIME=str(desktop_codex),
        MAINFRAME_INSTALL_TESTING="1",
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


def test_reinstall_removes_unchanged_retired_managed_artifact():
    home = pathlib.Path(tempfile.mkdtemp())
    source = home / "retired-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("retired\n", encoding="utf-8")
    target = home / ".agents" / "skills" / "retired-skill"
    state = home / ".codex" / ".mainframe-managed-artifacts" / "skill-retired.json"
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
    for child in source.iterdir():
        child.unlink()
    source.rmdir()

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    assert not target.exists()
    assert not state.exists()


def test_dry_run_reports_direct_cross_surface_delivery():
    proc, home = _run("--codex", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "managed copy" in proc.stdout
    assert "mainframe-init" in proc.stdout
    assert "mainframe-opencode" in proc.stdout
    assert "mainframe-pi-business-analysis" in proc.stdout
    assert "mainframe-secrets" in proc.stdout
    assert "mainframe-ticket" in proc.stdout
    assert "mainframe-tickets-find" in proc.stdout
    assert "mainframe-tickets-refine" in proc.stdout
    assert "mainframe-tickets-implement" in proc.stdout
    assert "mainframe-tickets-verify" in proc.stdout
    assert "mainframe-python-backend" in proc.stdout
    assert "mainframe-typescript-backend" in proc.stdout
    assert "mainframe-frontend" in proc.stdout
    assert "mainframe-testing-strategy" in proc.stdout
    assert "mainframe-infrastructure" in proc.stdout
    assert "mainframe-curl-requests" in proc.stdout
    assert "mainframe-ops-app-server-safety" in proc.stdout
    assert "mainframe.rules" in proc.stdout
    assert "hook groups" in proc.stdout
    assert "mainframe_researcher.toml" in proc.stdout
    assert "mainframe_python_backend_engineer.toml" in proc.stdout
    assert "mainframe_typescript_backend_engineer.toml" in proc.stdout
    assert "mainframe_react_frontend_engineer.toml" in proc.stdout
    assert "mainframe_test_auditor.toml" in proc.stdout
    assert "mainframe_decision_reviewer.toml" in proc.stdout
    assert "mainframe_advisor.toml" in proc.stdout
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_preflight_consumes_the_complete_feature_list():
    proc, home = _run("--codex", "--dry-run", feature_rows=4096)
    assert proc.returncode == 0, proc.stderr
    assert "Codex adapter preflight passed" in proc.stdout
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_clean_install_probes_runtime_without_precreating_codex_home():
    proc, home = _run(
        "--codex", "--dry-run", require_existing_codex_home=True
    )
    assert proc.returncode == 0, proc.stderr
    assert "Codex adapter preflight passed" in proc.stdout
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_install_stops_when_desktop_runtime_lacks_native_hooks():
    proc, home = _run(
        "--codex",
        "--dry-run",
        desktop_hooks_supported=False,
    )
    assert proc.returncode != 0
    assert "Desktop runtime does not expose stable native hooks" in proc.stderr
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()


def test_clean_install_is_idempotent_and_uninstall_preserves_shared_secrets():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr

    codex_dir = home / ".codex"
    agents = codex_dir / "AGENTS.md"
    state = codex_dir / ".mainframe-managed-artifacts" / "global-agents.json"
    index_state = codex_dir / ".mainframe-index-state"
    assert agents.is_file() and not agents.is_symlink()
    assert agents.read_bytes() == (ADAPTER / "export" / "AGENTS.md").read_bytes()
    assert state.is_file()
    assert stat.S_IMODE(agents.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.stat().st_mode) == 0o600

    for name in (
        "mainframe-init",
        "mainframe-pi-business-analysis",
        "mainframe-secrets",
        "mainframe-ticket",
        "mainframe-tickets-find",
        "mainframe-tickets-refine",
        "mainframe-tickets-implement",
        "mainframe-tickets-verify",
        "mainframe-python-backend",
        "mainframe-typescript-backend",
        "mainframe-frontend",
        "mainframe-testing-strategy",
        "mainframe-infrastructure",
        "mainframe-curl-requests",
        "mainframe-ops-app-server-safety",
        ):
        target = home / ".agents" / "skills" / name
        assert target.is_dir() and not target.is_symlink()
        assert (target / "SKILL.md").read_bytes() == (
            ADAPTER / "skills" / name / "SKILL.md"
        ).read_bytes()

    index = codex_dir / "credentials-index.md"
    helper = home / ".local" / "bin" / "secret"
    opencode_launcher = home / ".local" / "bin" / "mainframe-opencode"
    assert opencode_launcher.is_file() and not opencode_launcher.is_symlink()
    assert opencode_launcher.read_bytes() == (ADAPTER / "bin" / "mainframe-opencode").read_bytes()
    assert index.is_symlink() and index.resolve() == SHARED / "credentials-index.md"
    assert index_state.is_file()
    rules = codex_dir / "rules" / "mainframe.rules"
    rules_state = codex_dir / ".mainframe-managed-artifacts" / "rules.json"
    assert rules.is_file() and not rules.is_symlink()
    assert rules.read_bytes() == (ADAPTER / "rules" / "mainframe.rules").read_bytes()
    assert rules_state.is_file()
    researcher = codex_dir / "agents" / "mainframe_researcher.toml"
    researcher_state = codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_researcher.json"
    assert researcher.is_file() and not researcher.is_symlink()
    assert researcher_state.is_file()
    researcher_data = tomllib.loads(researcher.read_text(encoding="utf-8"))
    assert researcher_data["name"] == "mainframe_researcher"
    assert researcher_data["model"] == "gpt-5.6-terra"
    assert researcher_data["model_reasoning_effort"] == "medium"
    assert researcher_data["sandbox_mode"] == "read-only"
    assert researcher_data["web_search"] == "live"
    assert researcher_data["features"]["apps"] is False
    assert researcher_data["features"]["shell_tool"] is False
    assert researcher_data["features"]["unified_exec"] is False
    assert researcher_data["skills"]["config"] == [
        {
            "path": str(
                codex_dir
                / "mainframe"
                / "private-skills"
                / "mainframe-research-method"
                / "SKILL.md"
            ),
            "enabled": True,
        }
    ]
    assert not (
        home / ".agents" / "skills" / "mainframe-research-method"
    ).exists()
    typescript_engineer = (
        codex_dir / "agents" / "mainframe_typescript_backend_engineer.toml"
    )
    typescript_state = (
        codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_typescript_backend_engineer.json"
    )
    assert typescript_engineer.is_file() and not typescript_engineer.is_symlink()
    assert typescript_state.is_file()
    typescript_data = tomllib.loads(typescript_engineer.read_text(encoding="utf-8"))
    assert typescript_data["name"] == "mainframe_typescript_backend_engineer"
    assert "model" not in typescript_data
    assert "model_reasoning_effort" not in typescript_data
    assert typescript_data["sandbox_mode"] == "workspace-write"
    assert typescript_data["web_search"] == "live"
    assert typescript_data["features"]["apps"] is False
    assert typescript_data["skills"]["config"] == [
        {
            "path": str(
                home
                / ".agents"
                / "skills"
                / "mainframe-typescript-backend"
                / "SKILL.md"
            ),
            "enabled": True,
        },
        {
            "path": str(
                home / ".agents" / "skills" / "mainframe-ticket" / "SKILL.md"
            ),
            "enabled": True,
        },
    ]
    python_engineer = codex_dir / "agents" / "mainframe_python_backend_engineer.toml"
    python_state = codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_python_backend_engineer.json"
    assert python_engineer.is_file() and not python_engineer.is_symlink()
    assert python_state.is_file()
    python_data = tomllib.loads(python_engineer.read_text(encoding="utf-8"))
    assert python_data["name"] == "mainframe_python_backend_engineer"
    assert "model" not in python_data
    assert "model_reasoning_effort" not in python_data
    assert python_data["sandbox_mode"] == "workspace-write"
    assert python_data["web_search"] == "live"
    assert python_data["features"]["apps"] is False
    assert [item["path"] for item in python_data["skills"]["config"]] == [
        str(
            home
            / ".agents"
            / "skills"
            / "mainframe-python-backend"
            / "SKILL.md"
        ),
        str(home / ".agents" / "skills" / "mainframe-ticket" / "SKILL.md"),
    ]
    frontend_engineer = codex_dir / "agents" / "mainframe_react_frontend_engineer.toml"
    frontend_state = (
        codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_react_frontend_engineer.json"
    )
    assert frontend_engineer.is_file() and not frontend_engineer.is_symlink()
    assert frontend_state.is_file()
    frontend_data = tomllib.loads(frontend_engineer.read_text(encoding="utf-8"))
    assert frontend_data["name"] == "mainframe_react_frontend_engineer"
    assert "model" not in frontend_data
    assert "model_reasoning_effort" not in frontend_data
    assert frontend_data["sandbox_mode"] == "workspace-write"
    assert frontend_data["web_search"] == "live"
    assert frontend_data["features"]["apps"] is False
    assert [item["path"] for item in frontend_data["skills"]["config"]] == [
        str(home / ".agents" / "skills" / "mainframe-frontend" / "SKILL.md"),
        str(home / ".agents" / "skills" / "mainframe-ticket" / "SKILL.md"),
    ]
    test_auditor = codex_dir / "agents" / "mainframe_test_auditor.toml"
    test_auditor_state = (
        codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_test_auditor.json"
    )
    assert test_auditor.is_file() and not test_auditor.is_symlink()
    assert test_auditor_state.is_file()
    test_auditor_data = tomllib.loads(test_auditor.read_text(encoding="utf-8"))
    assert test_auditor_data["name"] == "mainframe_test_auditor"
    assert "model" not in test_auditor_data
    assert "model_reasoning_effort" not in test_auditor_data
    assert test_auditor_data["sandbox_mode"] == "workspace-write"
    assert "default_permissions" not in test_auditor_data
    assert "permissions" not in test_auditor_data
    assert test_auditor_data["web_search"] == "live"
    assert test_auditor_data["features"]["apps"] is False
    assert [item["path"] for item in test_auditor_data["skills"]["config"]] == [
        str(
            home
            / ".agents"
            / "skills"
            / "mainframe-testing-strategy"
            / "SKILL.md"
        ),
        str(home / ".agents" / "skills" / "mainframe-ticket" / "SKILL.md"),
    ]
    decision_reviewer = codex_dir / "agents" / "mainframe_decision_reviewer.toml"
    decision_reviewer_state = (
        codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_decision_reviewer.json"
    )
    assert decision_reviewer.is_file() and not decision_reviewer.is_symlink()
    assert decision_reviewer_state.is_file()
    decision_reviewer_data = tomllib.loads(
        decision_reviewer.read_text(encoding="utf-8")
    )
    assert decision_reviewer_data["name"] == "mainframe_decision_reviewer"
    assert "model" not in decision_reviewer_data
    assert "model_reasoning_effort" not in decision_reviewer_data
    assert decision_reviewer_data["sandbox_mode"] == "read-only"
    assert decision_reviewer_data["web_search"] == "live"
    assert decision_reviewer_data["features"]["apps"] is False
    assert decision_reviewer_data["skills"]["config"] == [
        {
            "path": str(
                codex_dir
                / "mainframe"
                / "private-skills"
                / "mainframe-decision-review"
                / "SKILL.md"
            ),
            "enabled": True,
        }
    ]
    assert not (
        home / ".agents" / "skills" / "mainframe-decision-review"
    ).exists()
    advisor = codex_dir / "agents" / "mainframe_advisor.toml"
    advisor_state = codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_advisor.json"
    assert advisor.is_file() and not advisor.is_symlink()
    assert advisor_state.is_file()
    advisor_data = tomllib.loads(advisor.read_text(encoding="utf-8"))
    assert advisor_data["name"] == "mainframe_advisor"
    assert advisor_data["model"] == "gpt-5.6-sol"
    assert advisor_data["model_reasoning_effort"] == "high"
    assert advisor_data["sandbox_mode"] == "read-only"
    assert advisor_data["web_search"] == "live"
    assert advisor_data["features"]["apps"] is False
    assert advisor_data["skills"]["config"] == [
        {
            "path": str(
                codex_dir
                / "mainframe"
                / "private-skills"
                / "mainframe-readiness-review"
                / "SKILL.md"
            ),
            "enabled": True,
        }
    ]
    assert not (
        home / ".agents" / "skills" / "mainframe-readiness-review"
    ).exists()
    config = codex_dir / "config.toml"
    config_state = codex_dir / ".mainframe-config-state.json"
    assert not config.exists()
    assert not config_state.exists()
    hooks = codex_dir / "hooks.json"
    hooks_state = codex_dir / ".mainframe-hooks-state.json"
    assert hooks.is_file() and hooks_state.is_file()
    hooks_data = json.loads(hooks.read_text(encoding="utf-8"))
    assert set(hooks_data["hooks"]) == {
        "SessionStart", "SessionEnd", "SubagentStart", "PreToolUse",
        "PermissionRequest", "PostToolUse", "PostCompact",
        "UserPromptSubmit", "Stop", "SubagentStop",
    }
    permission_groups = hooks_data["hooks"]["PermissionRequest"]
    assert permission_groups[0]["matcher"] == ".*"
    assert (ADAPTER / "hooks" / "scripts" / "_permission_audit.py").is_file()
    assert stat.S_IMODE(hooks.stat().st_mode) == 0o600
    assert stat.S_IMODE(hooks_state.stat().st_mode) == 0o600
    commands = [
        handler["command"]
        for groups in hooks_data["hooks"].values()
        for group in groups
        for handler in group["hooks"]
    ]
    assert commands and all(
        command.startswith("python3 -B ")
        and str((ADAPTER / "hooks" / "scripts" / "mainframe-hook.py").resolve())
        in command
        for command in commands
    )
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
    assert not researcher.exists() and not researcher.is_symlink()
    assert not researcher_state.exists()
    assert not typescript_engineer.exists() and not typescript_engineer.is_symlink()
    assert not typescript_state.exists()
    assert not python_engineer.exists() and not python_engineer.is_symlink()
    assert not python_state.exists()
    assert not frontend_engineer.exists() and not frontend_engineer.is_symlink()
    assert not frontend_state.exists()
    assert not test_auditor.exists() and not test_auditor.is_symlink()
    assert not test_auditor_state.exists()
    assert not decision_reviewer.exists()
    assert not decision_reviewer_state.exists()
    assert not advisor.exists()
    assert not advisor_state.exists()
    assert not opencode_launcher.exists() and not opencode_launcher.is_symlink()
    assert not config.exists()
    assert not config_state.exists()
    assert not hooks.exists()
    assert not hooks_state.exists()
    assert helper.is_symlink()
    for name in (
        "mainframe-init",
        "mainframe-pi-business-analysis",
        "mainframe-secrets",
        "mainframe-ticket",
        "mainframe-tickets-find",
        "mainframe-tickets-refine",
        "mainframe-tickets-implement",
        "mainframe-tickets-verify",
        "mainframe-python-backend",
        "mainframe-typescript-backend",
        "mainframe-frontend",
        "mainframe-testing-strategy",
        "mainframe-infrastructure",
        "mainframe-curl-requests",
        "mainframe-ops-app-server-safety",
    ):
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
    assert "pre-existing content" in refused.stderr
    assert target.read_text(encoding="utf-8") == "personal instructions\n"
    assert not (home / ".local" / "bin" / "secret").exists()

    installed, _ = _run("--codex", "--replace-modified", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.read_bytes() == (ADAPTER / "export" / "AGENTS.md").read_bytes()
    managed_state = json.loads(
        (codex_dir / ".mainframe-managed-artifacts" / "global-agents.json").read_text(
            encoding="utf-8"
        )
    )
    backup = pathlib.Path(managed_state["original_backup"])
    assert backup.read_text(encoding="utf-8") == "personal instructions\n"

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.read_text(encoding="utf-8") == "personal instructions\n"
    assert not backup.exists()


def test_changed_managed_agents_is_preserved_on_uninstall():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "AGENTS.md"
    target.write_text("user changed this file\n", encoding="utf-8")

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "local changes" in removed.stderr
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
    assert "pre-existing content" in refused.stderr
    assert target.read_text(encoding="utf-8") == "# user-owned rules\n"

    installed, _ = _run("--codex", "--replace-modified", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.is_file() and not target.is_symlink()
    assert target.read_bytes() == (ADAPTER / "rules" / "mainframe.rules").read_bytes()

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.is_file() and not target.is_symlink()
    assert target.read_text(encoding="utf-8") == "# user-owned rules\n"


def test_existing_user_hooks_are_merged_and_restored_on_uninstall():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    target = codex_dir / "hooks.json"
    user_group = {
        "matcher": "^Bash$",
        "hooks": [{"type": "command", "command": "python3 user-hook.py"}],
    }
    target.write_text(
        json.dumps({"description": "kept", "hooks": {"PreToolUse": [user_group]}}),
        encoding="utf-8",
    )

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    current = json.loads(target.read_text(encoding="utf-8"))
    assert current["description"] == "kept"
    assert user_group in current["hooks"]["PreToolUse"]

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    restored = json.loads(target.read_text(encoding="utf-8"))
    assert restored == {
        "description": "kept",
        "hooks": {"PreToolUse": [user_group]},
    }


def test_changed_managed_hook_stops_uninstall_before_other_removal():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "hooks.json"
    document = json.loads(target.read_text(encoding="utf-8"))
    document["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 1
    target.write_text(json.dumps(document), encoding="utf-8")

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "changed or is duplicated" in removed.stderr
    assert target.exists()
    assert (home / ".codex" / "AGENTS.md").is_file()
    assert (home / ".agents" / "skills" / "mainframe-init").is_dir()
    assert not (home / ".agents" / "skills" / "mainframe-init").is_symlink()


def test_existing_mainframe_researcher_requires_yes_and_is_restored():
    home = pathlib.Path(tempfile.mkdtemp())
    agents_dir = home / ".codex" / "agents"
    agents_dir.mkdir(parents=True)
    target = agents_dir / "mainframe_researcher.toml"
    target.write_text(
        'name = "personal"\n'
        'description = "Personal researcher."\n'
        'developer_instructions = "Keep me."\n',
        encoding="utf-8",
    )

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "pre-existing content" in refused.stderr
    assert 'name = "personal"' in target.read_text(encoding="utf-8")

    installed, _ = _run("--codex", "--replace-modified", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.is_file() and not target.is_symlink()
    assert tomllib.loads(target.read_text(encoding="utf-8"))["name"] == (
        "mainframe_researcher"
    )

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.is_file() and not target.is_symlink()
    assert 'name = "personal"' in target.read_text(encoding="utf-8")


def test_legacy_symlinked_researcher_migrates_without_user_backup():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    agents_dir = codex_dir / "agents"
    agents_dir.mkdir(parents=True)
    target = agents_dir / "mainframe_researcher.toml"
    target.symlink_to(ADAPTER / "agents" / "mainframe_researcher.toml")
    state = codex_dir / ".mainframe-agent-mainframe_researcher-state"
    state.write_text("backup_path=-\n", encoding="utf-8")

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.is_file() and not target.is_symlink()
    managed_state = codex_dir / ".mainframe-managed-artifacts" / "agent-mainframe_researcher.json"
    assert managed_state.is_file()
    assert not state.exists()

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert not target.exists() and not target.is_symlink()
    assert not state.exists()


def test_existing_decision_reviewer_requires_yes_and_is_restored():
    home = pathlib.Path(tempfile.mkdtemp())
    agents_dir = home / ".codex" / "agents"
    agents_dir.mkdir(parents=True)
    target = agents_dir / "mainframe_decision_reviewer.toml"
    target.write_text(
        'name = "personal_reviewer"\n'
        'description = "Personal reviewer."\n'
        'developer_instructions = "Keep me."\n',
        encoding="utf-8",
    )

    refused, _ = _run("--codex", home=home)
    assert refused.returncode != 0
    assert "pre-existing content" in refused.stderr
    assert 'name = "personal_reviewer"' in target.read_text(encoding="utf-8")

    installed, _ = _run("--codex", "--replace-modified", home=home)
    assert installed.returncode == 0, installed.stderr
    assert target.is_file() and not target.is_symlink()
    assert tomllib.loads(target.read_text(encoding="utf-8"))["name"] == (
        "mainframe_decision_reviewer"
    )

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert target.is_file() and not target.is_symlink()
    assert 'name = "personal_reviewer"' in target.read_text(encoding="utf-8")


def test_changed_mainframe_rules_stop_uninstall_before_other_removal():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "rules" / "mainframe.rules"
    target.unlink()
    target.write_text("# changed after install\n", encoding="utf-8")

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "local changes" in removed.stderr
    assert target.read_text(encoding="utf-8") == "# changed after install\n"
    assert (home / ".codex" / "AGENTS.md").is_file()
    assert (home / ".agents" / "skills" / "mainframe-init").is_dir()
    assert not (home / ".agents" / "skills" / "mainframe-init").is_symlink()


def test_changed_mainframe_researcher_stops_uninstall_before_other_removal():
    installed, home = _run("--codex")
    assert installed.returncode == 0, installed.stderr
    target = home / ".codex" / "agents" / "mainframe_researcher.toml"
    target.unlink()
    target.write_text(
        'name = "changed"\n'
        'description = "Changed after install."\n'
        'developer_instructions = "Preserve this."\n',
        encoding="utf-8",
    )

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode != 0
    assert "local changes" in removed.stderr
    assert 'name = "changed"' in target.read_text(encoding="utf-8")
    assert (home / ".codex" / "AGENTS.md").is_file()


def test_existing_config_is_untouched_by_normal_install_and_uninstall():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    config = codex_dir / "config.toml"
    original = (
        'model = "example"\n'
        'default_permissions = ":danger-full-access"\n\n'
        '[mcp_servers.example]\n'
        'command = "example"\n'
    )
    config.write_text(original, encoding="utf-8")

    installed, _ = _run("--codex", home=home)
    assert installed.returncode == 0, installed.stderr
    assert config.read_text(encoding="utf-8") == original
    assert not (codex_dir / ".mainframe-config-state.json").exists()

    removed, _ = _run("--codex", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert config.read_text(encoding="utf-8") == original


def test_existing_managed_permissions_are_retired_and_user_settings_restored():
    home = pathlib.Path(tempfile.mkdtemp())
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    config = codex_dir / "config.toml"
    state_path = codex_dir / ".mainframe-config-state.json"
    block = (
        "# >>> MAINFRAME CODEX PERMISSIONS >>>\n"
        'default_permissions = "mainframe"\n'
        'permissions.mainframe.extends = ":workspace"\n'
        "# <<< MAINFRAME CODEX PERMISSIONS <<<\n\n"
    )
    feature = (
        "# >>> MAINFRAME CODEX NETWORK PROXY >>>\n"
        "network_proxy = true\n"
        "# <<< MAINFRAME CODEX NETWORK PROXY <<<\n"
    )
    config.write_text(
        block + 'model = "kept"\n\n[features]\n' + feature + 'apps = true\n',
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(
            {
                "managed_sha": hashlib.sha256(block.encode()).hexdigest(),
                "feature_managed_sha": hashlib.sha256(feature.encode()).hexdigest(),
                "feature_table_created": False,
                "removed": [
                    {"kind": "top", "text": 'approval_policy = "on-request"\n'},
                    {"kind": "top", "text": 'sandbox_mode = "workspace-write"\n'},
                ],
            }
        ),
        encoding="utf-8",
    )

    migrated, _ = _run("--codex", home=home)
    assert migrated.returncode == 0, migrated.stderr
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert data["model"] == "kept"
    assert data["approval_policy"] == "on-request"
    assert data["sandbox_mode"] == "workspace-write"
    assert data["features"] == {"apps": True}
    assert "default_permissions" not in data
    assert "permissions" not in data
    assert not state_path.exists()


def test_skill_collision_stops_before_shared_install():
    home = pathlib.Path(tempfile.mkdtemp())
    collision = home / ".agents" / "skills" / "mainframe-init"
    collision.mkdir(parents=True)
    (collision / "SKILL.md").write_text("unrelated\n", encoding="utf-8")

    proc, _ = _run("--codex", home=home)
    assert proc.returncode != 0
    assert "pre-existing content" in proc.stderr
    assert not (home / ".local" / "bin" / "secret").exists()
    assert (collision / "SKILL.md").read_text(encoding="utf-8") == "unrelated\n"


def test_dev_mode_initializes_only_codex_owned_telemetry():
    proc, home = _run("--codex", "--dev")
    assert proc.returncode == 0, proc.stderr
    telemetry = home / ".codex" / "mainframe" / "codex" / "telemetry"
    db = telemetry / "telemetry.db"
    assert db.is_file()
    assert (telemetry / "enabled").is_file()
    feedback = home / ".agents" / "skills" / "harness-feedback"
    assert feedback.is_dir() and not feedback.is_symlink()
    assert (feedback / "SKILL.md").read_bytes() == (
        ADAPTER / "dev" / "skills" / "harness-feedback" / "SKILL.md"
    ).read_bytes()
    opencode = home / ".local" / "bin" / "mainframe-opencode"
    assert opencode.is_file() and not opencode.is_symlink()
    assert opencode.read_bytes() == (ADAPTER / "bin" / "mainframe-opencode").read_bytes()
    assert not (home / ".claude" / "mainframe").exists()
    config = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert config["otel"] == {
        "environment": "mainframe-dev",
        "exporter": {
            "otlp-http": {
                "endpoint": "http://127.0.0.1:4318/v1/logs",
                "protocol": "binary",
            }
        },
        "log_user_prompt": False,
    }

    normal, _ = _run("--codex", home=home)
    assert normal.returncode == 0, normal.stderr
    assert db.is_file()
    assert not (telemetry / "enabled").exists()
    assert not feedback.exists()
    assert not (home / ".codex" / "config.toml").exists()


def test_normal_install_leaves_codex_telemetry_inactive():
    proc, home = _run("--codex")
    assert proc.returncode == 0, proc.stderr
    assert not (home / ".codex" / "mainframe" / "codex" / "telemetry").exists()
    assert not (home / ".agents" / "skills" / "harness-feedback").exists()
    launcher = home / ".local" / "bin" / "mainframe-opencode"
    assert launcher.is_file() and not launcher.is_symlink()


def test_peer_advisor_is_explicit_optional_and_reversible():
    missing, missing_home = _run("--codex", "--with-peer-advisor")
    assert missing.returncode != 0
    assert "requires the Claude Code CLI" in missing.stderr
    assert not (missing_home / ".agents" / "skills" / "mainframe-peer-review").exists()

    installed, home = _run("--codex", "--with-peer-advisor", claude_peer=True)
    assert installed.returncode == 0, installed.stderr
    target = home / ".agents" / "skills" / "mainframe-peer-review"
    assert target.is_dir() and not target.is_symlink()
    body = (target / "SKILL.md").read_text(encoding="utf-8")
    assert "claude -p --safe-mode" in body
    assert "--dangerously-skip-permissions" in body
    metadata = (target / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" not in metadata

    plain, _ = _run("--codex", home=home, claude_peer=True)
    assert plain.returncode == 0, plain.stderr
    assert not target.exists()


def test_baseline_uses_native_standalone_layers_only():
    assert not (ADAPTER / "plugin").exists()
    assert (ADAPTER / "hooks" / "hooks.json").is_file()
    assert (ADAPTER / "hooks" / "scripts" / "mainframe-hook.py").is_file()
    assert not (ADAPTER / "config.toml").exists()
    template_home = pathlib.Path("/tmp/mainframe-codex-template-home")
    researcher = ADAPTER / "agents" / "mainframe_researcher.toml.template"
    assert researcher.is_file()
    researcher_data = _agent_template_data(
        "mainframe_researcher", home=template_home
    )
    assert researcher_data["description"].startswith("Use for a bounded external-research block")
    assert "Do not use for repository exploration" in researcher_data["description"]
    assert "Do not inspect the repository" in researcher_data["developer_instructions"]
    assert researcher_data["skills"]["config"] == [
        {
                "path": str((
                        template_home
                    / ".codex"
                    / "mainframe"
                    / "private-skills"
                    / "mainframe-research-method"
                        / "SKILL.md"
                ).resolve()),
            "enabled": True,
        }
    ]
    typescript_engineer = (
        ADAPTER / "agents" / "mainframe_typescript_backend_engineer.toml.template"
    )
    assert typescript_engineer.is_file()
    typescript_data = _agent_template_data(
        "mainframe_typescript_backend_engineer", home=template_home
    )
    assert "model" not in typescript_data
    assert "model_reasoning_effort" not in typescript_data
    assert "load and follow" not in (
        typescript_data["developer_instructions"].lower()
    )
    assert "stage files, commit, push" in typescript_data["developer_instructions"]
    assert len(typescript_data["skills"]["config"]) == 2
    python_engineer = (
        ADAPTER / "agents" / "mainframe_python_backend_engineer.toml.template"
    )
    assert python_engineer.is_file()
    python_data = _agent_template_data(
        "mainframe_python_backend_engineer", home=template_home
    )
    assert "model" not in python_data
    assert "model_reasoning_effort" not in python_data
    assert "load and follow" not in python_data["developer_instructions"].lower()
    assert "stage files, commit, push" in python_data["developer_instructions"]
    assert len(python_data["skills"]["config"]) == 2
    frontend_engineer = (
        ADAPTER / "agents" / "mainframe_react_frontend_engineer.toml.template"
    )
    assert frontend_engineer.is_file()
    frontend_data = _agent_template_data(
        "mainframe_react_frontend_engineer", home=template_home
    )
    assert "model" not in frontend_data
    assert "model_reasoning_effort" not in frontend_data
    assert "load and follow" not in frontend_data["developer_instructions"].lower()
    assert "stage files, commit, push" in frontend_data["developer_instructions"]
    assert len(frontend_data["skills"]["config"]) == 2
    test_auditor = ADAPTER / "agents" / "mainframe_test_auditor.toml.template"
    assert test_auditor.is_file()
    test_auditor_data = _agent_template_data(
        "mainframe_test_auditor", home=template_home
    )
    assert "model" not in test_auditor_data
    assert "model_reasoning_effort" not in test_auditor_data
    assert test_auditor_data["sandbox_mode"] == "workspace-write"
    assert "load and follow" not in (
        test_auditor_data["developer_instructions"].lower()
    )
    assert "Do not implement fixes" in test_auditor_data["developer_instructions"]
    assert "default_permissions" not in test_auditor_data
    assert "permissions" not in test_auditor_data
    assert len(test_auditor_data["skills"]["config"]) == 2
    decision_reviewer_template = (
        ADAPTER / "agents" / "mainframe_decision_reviewer.toml.template"
    )
    assert decision_reviewer_template.is_file()
    decision_reviewer_data = tomllib.loads(
        decision_reviewer_template.read_text(encoding="utf-8").replace(
            "__MAINFRAME_DECISION_REVIEW_SKILL__",
            "/tmp/mainframe-decision-review/SKILL.md",
        )
    )
    assert "model" not in decision_reviewer_data
    assert "model_reasoning_effort" not in decision_reviewer_data
    assert decision_reviewer_data["sandbox_mode"] == "read-only"
    assert decision_reviewer_data["web_search"] == "live"
    assert decision_reviewer_data["features"]["apps"] is False
    assert decision_reviewer_data["skills"]["config"] == [
        {
            "path": "/tmp/mainframe-decision-review/SKILL.md",
            "enabled": True,
        }
    ]
    private_review_skill = ADAPTER / "skills" / "mainframe-decision-review"
    private_review_body = (private_review_skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-decision-review" in private_review_body
    assert "ASSESSMENT:" in private_review_body
    assert not (private_review_skill / "agents" / "openai.yaml").exists()
    advisor_template = ADAPTER / "agents" / "mainframe_advisor.toml.template"
    assert advisor_template.is_file()
    advisor_data = tomllib.loads(
        advisor_template.read_text(encoding="utf-8").replace(
            "__MAINFRAME_READINESS_REVIEW_SKILL__",
            "/tmp/mainframe-readiness-review/SKILL.md",
        )
    )
    assert advisor_data["model"] == "gpt-5.6-sol"
    assert advisor_data["model_reasoning_effort"] == "high"
    assert advisor_data["sandbox_mode"] == "read-only"
    assert advisor_data["web_search"] == "live"
    assert advisor_data["features"]["apps"] is False
    assert advisor_data["skills"]["config"] == [
        {
            "path": "/tmp/mainframe-readiness-review/SKILL.md",
            "enabled": True,
        }
    ]
    private_readiness_skill = ADAPTER / "skills" / "mainframe-readiness-review"
    private_readiness_body = (private_readiness_skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-readiness-review" in private_readiness_body
    assert "VERDICT:" in private_readiness_body
    assert not (private_readiness_skill / "agents" / "openai.yaml").exists()
    private_research_skill = ADAPTER / "skills" / "mainframe-research-method"
    private_research_body = (private_research_skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-research-method" in private_research_body
    assert "references/software-documentation.md" in private_research_body
    assert "references/economics.md" in private_research_body
    assert "references/news.md" in private_research_body
    assert not (private_research_skill / "agents" / "openai.yaml").exists()
    assert (ADAPTER / "rules" / "mainframe.rules").is_file()
    rules_body = (
        ADAPTER / "rules" / "mainframe.rules"
    ).read_text(encoding="utf-8")
    assert 'pattern = ["secret"]' not in rules_body
    assert 'pattern = ["mainframe-pi", "business-analysis"]' not in rules_body
    assert 'pattern = ["mainframe-opencode"]' not in rules_body
    assert 'pattern = ["git", ["add", "stage", "commit"' not in rules_body
    assert 'pattern = ["git", ["commit-tree", "send-pack"]]' in rules_body
    assert 'decision = "forbidden"' in rules_body
    assert 'decision = "prompt"' not in rules_body
    assert '"git worktree prune"' not in rules_body
    assert not (ADAPTER / "config" / "mainframe-permissions.toml").exists()
    assert (ADAPTER / "scripts" / "manage-config.py").is_file()
    assert (ADAPTER / "scripts" / "manage-hooks.py").is_file()

    init_metadata = (
        ADAPTER / "skills" / "mainframe-init" / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in init_metadata
    assert "/goal" not in (
        ADAPTER / "skills" / "mainframe-init" / "SKILL.md"
    ).read_text(encoding="utf-8")

    ticket_skill = ADAPTER / "skills" / "mainframe-ticket"
    ticket_body = (ticket_skill / "SKILL.md").read_text(encoding="utf-8")
    ticket_metadata = (ticket_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-ticket" in ticket_body
    assert "record-observation.md" in ticket_body
    assert "record-confirmed-problem.md" in ticket_body
    assert "ticket-format.md" in ticket_body
    assert "allow_implicit_invocation" not in ticket_metadata
    for reference in (
        "record-observation.md",
        "record-confirmed-problem.md",
        "ticket-format.md",
    ):
        assert (ticket_skill / "references" / reference).is_file()

    find_skill = ADAPTER / "skills" / "mainframe-tickets-find"
    find_body = (find_skill / "SKILL.md").read_text(encoding="utf-8")
    find_metadata = (find_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-tickets-find" in find_body
    assert "record-observation.md" in find_body
    assert "ticket-format.md" in find_body
    assert "native Goal" in find_body
    assert "Do not run project code" in find_body
    assert (
        "Do not claim that the repository has no remaining defects" in find_body
    )
    assert "allow_implicit_invocation: false" in find_metadata

    refine_skill = ADAPTER / "skills" / "mainframe-tickets-refine"
    refine_body = (refine_skill / "SKILL.md").read_text(encoding="utf-8")
    refine_metadata = (refine_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-tickets-refine" in refine_body
    assert "ticket-format.md" in refine_body
    assert "native Goal" in refine_body
    assert "Do not run project code" in refine_body
    assert "semantic duplicates" in refine_body
    assert "open/needs-scope-review/" in refine_body
    assert "open/needs-decision/" in refine_body
    assert "open/ready/" in refine_body
    assert "archive/rejected/" in refine_body
    assert "allow_implicit_invocation: false" in refine_metadata

    implement_skill = ADAPTER / "skills" / "mainframe-tickets-implement"
    implement_body = (implement_skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    implement_metadata = (
        implement_skill / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "name: mainframe-tickets-implement" in implement_body
    assert "ticket-format.md" in implement_body
    assert "mainframe-testing-strategy" in implement_body
    assert "native Goal" in implement_body
    assert "open/ready/" in implement_body
    assert "open/needs-verification/" in implement_body
    assert "open/needs-scope-review/" in implement_body
    assert "open/needs-decision/" in implement_body
    assert "Do not independently close" in implement_body
    assert "Conventional Commit" in implement_body
    assert "allow_implicit_invocation: false" in implement_metadata

    verify_skill = ADAPTER / "skills" / "mainframe-tickets-verify"
    verify_body = (verify_skill / "SKILL.md").read_text(encoding="utf-8")
    verify_metadata = (
        verify_skill / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")
    assert "name: mainframe-tickets-verify" in verify_body
    assert "ticket-format.md" in verify_body
    assert "mainframe-testing-strategy" in verify_body
    assert "native Goal" in verify_body
    assert "fresh task" in verify_body
    assert "Do not repair implementation code" in verify_body
    assert "open/needs-verification/" in verify_body
    assert "archive/resolved/" in verify_body
    assert "open/ready/" in verify_body
    assert "open/needs-scope-review/" in verify_body
    assert "open/needs-decision/" in verify_body
    assert "archive/rejected/" in verify_body
    assert "Conventional Commit" in verify_body
    assert "allow_implicit_invocation: false" in verify_metadata

    typescript_skill = ADAPTER / "skills" / "mainframe-typescript-backend"
    typescript_body = (typescript_skill / "SKILL.md").read_text(encoding="utf-8")
    assert "name: mainframe-typescript-backend" in typescript_body
    assert "scripts/recon.js" in typescript_body
    assert "references/testing.md" in typescript_body
    assert "mainframe-ticket" in typescript_body
    assert (typescript_skill / "scripts" / "recon.js").is_file()

    python_skill = ADAPTER / "skills" / "mainframe-python-backend"
    python_body = (python_skill / "SKILL.md").read_text(encoding="utf-8")
    python_metadata = (python_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-python-backend" in python_body
    assert "scripts/recon.py" in python_body
    assert "references/testing.md" in python_body
    assert "references/postgres-concurrency.md" in python_body
    assert "mainframe-ticket" in python_body
    assert "allow_implicit_invocation" not in python_metadata
    assert (python_skill / "scripts" / "recon.py").is_file()

    init_skill = ADAPTER / "skills" / "mainframe-init"
    init_body = (init_skill / "SKILL.md").read_text(encoding="utf-8")
    ticket_decision = (
        init_skill / "references" / "ticket-decision.md"
    ).read_text(encoding="utf-8")
    assert "one named ticket" in init_body
    assert "references/ticket-decision.md" in init_body
    assert "docs/tickets/open/needs-decision/" in ticket_decision
    assert "mainframe-testing-strategy" in ticket_decision
    assert "/goal Implement ticket <id>" in ticket_decision
    assert "docs/tickets/open/needs-verification/" in ticket_decision

    frontend_skill = ADAPTER / "skills" / "mainframe-frontend"
    frontend_body = (frontend_skill / "SKILL.md").read_text(encoding="utf-8")
    frontend_metadata = (frontend_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-frontend" in frontend_body
    assert "scripts/recon.js" in frontend_body
    assert "scripts/inspect-ui.mjs" in frontend_body
    assert "references/accessibility.md" in frontend_body
    assert "references/testing.md" in frontend_body
    assert "references/shadcn-composition.md" in frontend_body
    assert "mainframe-ticket" in frontend_body
    assert "allow_implicit_invocation" not in frontend_metadata
    assert (frontend_skill / "scripts" / "recon.js").is_file()
    assert (frontend_skill / "scripts" / "inspect-ui.mjs").is_file()

    testing_skill = ADAPTER / "skills" / "mainframe-testing-strategy"
    testing_body = (testing_skill / "SKILL.md").read_text(encoding="utf-8")
    testing_metadata = (testing_skill / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-testing-strategy" in testing_body
    assert "cheapest faithful observation" in testing_body
    assert "real local PostgreSQL" in testing_body
    assert "mainframe-ticket" in testing_body
    assert "--maxWorkers=2 --no-file-parallelism" in testing_body
    assert "Never use broad `pkill` or `killall`" in testing_body
    assert "allow_implicit_invocation" not in testing_metadata

    for path in (
        ADAPTER / "skills" / "mainframe-python-backend" / "references" / "testing.md",
        ADAPTER / "skills" / "mainframe-typescript-backend" / "references" / "testing.md",
        ADAPTER / "skills" / "mainframe-frontend" / "references" / "testing.md",
    ):
        body = path.read_text(encoding="utf-8")
        assert "never start" in body.lower()
        assert "pkill" in body and "killall" in body

    infrastructure_skill = ADAPTER / "skills" / "mainframe-infrastructure"
    infrastructure_body = (infrastructure_skill / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: mainframe-infrastructure" in infrastructure_body
    assert "references/infrastructure-map.md" in infrastructure_body
    assert "references/dokploy.md" in infrastructure_body
    assert (infrastructure_skill / "references" / "dokploy" / "safety.md").is_file()
    assert (infrastructure_skill / "agents" / "openai.yaml").is_file()

    curl_skill = ADAPTER / "skills" / "mainframe-curl-requests"
    curl_body = (curl_skill / "SKILL.md").read_text(encoding="utf-8")
    assert "name: mainframe-curl-requests" in curl_body
    assert "../../../../shared/credentials/credentials-index.md" in curl_body
    for skill in (ADAPTER / "skills" / "mainframe-secrets", curl_skill):
        assert (
            skill / "../../../../shared/credentials/credentials-index.md"
        ).resolve() == (SHARED / "credentials-index.md").resolve()
    assert (curl_skill / "agents" / "openai.yaml").is_file()

    server_skill = ADAPTER / "skills" / "mainframe-ops-app-server-safety"
    server_body = (server_skill / "SKILL.md").read_text(encoding="utf-8")
    assert "name: mainframe-ops-app-server-safety" in server_body
    assert "docker compose ps" in server_body
    assert (server_skill / "agents" / "openai.yaml").is_file()


def test_frontend_recon_routes_react_and_shadcn_context():
    package = pathlib.Path(tempfile.mkdtemp())
    ui = package / "src" / "components" / "ui"
    ui.mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps(
            {
                "name": "frontend-fixture",
                "dependencies": {
                    "react": "19.2.0",
                    "next": "16.1.0",
                    "@tanstack/react-query": "5.0.0",
                },
                "devDependencies": {
                    "typescript": "5.9.0",
                    "vitest": "3.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (package / "components.json").write_text(
        json.dumps(
            {
                "style": "new-york",
                "base": "radix",
                "rsc": True,
                "iconLibrary": "lucide",
                "aliases": {"ui": "@/components/ui"},
            }
        ),
        encoding="utf-8",
    )
    (ui / "button.tsx").write_text(
        "export function Button() { return null }\n", encoding="utf-8"
    )
    (package / "src" / "App.tsx").write_text(
        'import { Button } from "@/components/ui/button"\n', encoding="utf-8"
    )

    skill = ADAPTER / "skills" / "mainframe-frontend"
    recon = subprocess.run(
        ["node", str(skill / "scripts" / "recon.js"), str(package)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert recon.returncode == 0, recon.stderr
    recon_data = json.loads(recon.stdout)
    assert recon_data["runtime"]["react_declared"] == "19.2.0"
    assert recon_data["frameworks"]["next"] == "16.1.0"
    assert recon_data["ui"]["components_json"] is True
    assert recon_data["tests"]["vitest"] == "3.0.0"

    inspection = subprocess.run(
        ["node", str(skill / "scripts" / "inspect-ui.mjs"), str(package)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert inspection.returncode == 0, inspection.stderr
    inspection_data = json.loads(inspection.stdout)
    assert inspection_data["shadcn"] is True
    assert inspection_data["config"]["uiAlias"] == "@/components/ui"
    assert inspection_data["components"] == [
        {
            "name": "button",
            "file": "src/components/ui/button.tsx",
            "importedBy": ["src/App.tsx"],
        }
    ]

    unrelated = pathlib.Path(tempfile.mkdtemp())
    absent = subprocess.run(
        ["node", str(skill / "scripts" / "inspect-ui.mjs"), str(unrelated)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert absent.returncode == 0, absent.stderr
    assert json.loads(absent.stdout)["shadcn"] is False


def test_python_recon_reports_declared_stack_without_importing_it():
    package = pathlib.Path(tempfile.mkdtemp())
    (package / "pyproject.toml").write_text(
        """[project]
requires-python = ">=3.12"
dependencies = [
  "FastAPI==0.116.0",
  "SQLAlchemy>=2.0",
  "psycopg[binary]>=3.2",
  "pydantic>=2.11",
  "pytest>=8.4",
]

[tool.uv]

[tool.mypy]
strict = true
""",
        encoding="utf-8",
    )
    (package / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    recon = subprocess.run(
        [
            sys.executable,
            str(
                ADAPTER
                / "skills"
                / "mainframe-python-backend"
                / "scripts"
                / "recon.py"
            ),
            str(package),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert recon.returncode == 0, recon.stderr
    assert "python_requirement: >=3.12" in recon.stdout
    assert "package_manager: uv" in recon.stdout
    assert "frameworks: fastapi" in recon.stdout
    assert "data_access: psycopg+sqlalchemy" in recon.stdout
    assert "validation: pydantic" in recon.stdout
    assert "testing: pytest" in recon.stdout
    assert "type_checker: mypy" in recon.stdout


def test_shared_judgment_and_primary_completion_are_separated():
    global_body = (ADAPTER / "export" / "AGENTS.md").read_text(encoding="utf-8")
    normalized_global = " ".join(global_body.split())
    assert "accurate unfavorable finding" in normalized_global
    assert "Before a consequential action" in normalized_global
    assert "smallest adequate check" in normalized_global
    assert "narrow green check" in normalized_global
    assert "verified to run entirely on this machine" in normalized_global
    assert "without separate approval" in normalized_global
    assert "tunnel, proxy, or remote endpoint" in normalized_global
    assert "remote, shared, staging, or production endpoint" in normalized_global
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
    assert "mainframe_advisor" in normalized_init
    assert "preparation-readiness" in normalized_init
    assert "final-state" in normalized_init
    assert "set both its model and reasoning effort explicitly" in normalized_init
    assert "fastest adequate model" in normalized_init
    assert "silently inherits an expensive primary configuration" in normalized_init


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
