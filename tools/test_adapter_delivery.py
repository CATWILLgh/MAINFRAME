#!/usr/bin/env python3
"""Contract tests for adapter-scoped delivery.

Definition of done:
- the root installer is a no-op help entrypoint unless an adapter is selected;
- ``--claude`` routes through shared secrets and then the Claude Code adapter;
- Claude artifacts have one adapter-owned tree and no legacy root copies;
- specialists are delivered as user-level ``mainframe-*`` agents, outside the
  plugin boundary that drops agent-scoped hooks, MCP servers, and permissions;
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
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROOT_INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "claude-code"
PLUGIN = ADAPTER / "plugin"
AGENTS = ADAPTER / "agents"
SHARED_CREDENTIALS = ROOT / "shared" / "credentials"
ADAPTER_INSTALLER = ADAPTER / "install.sh"
MIN_CLAUDE_VERSION = re.search(
    r'^MIN_CLAUDE_VERSION="([0-9]+\.[0-9]+\.[0-9]+)"$',
    ADAPTER_INSTALLER.read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)


def _run_installer(*args, home=None, claude_version=None):
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
    for command in (
        "ruff", "oxlint",
        "fallow",
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
    assert sorted(home.iterdir()) == [home / "claude-version", home / "fake-bin"]


def test_root_dispatches_claude_dry_run():
    proc, _ = _run_installer("--claude", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "shared secrets" in proc.stdout.lower()
    assert "claude code adapter" in proc.stdout.lower()


def test_claude_dev_dry_run_is_adapter_scoped():
    proc, _ = _run_installer("--claude", "--dev", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "claude-code/{telemetry,feedback,model-lab}" in proc.stdout


def test_plain_reinstall_disables_owned_dev_links():
    installed, home = _run_installer("--claude")
    assert installed.returncode == 0, installed.stderr
    claude_dir = home / ".claude"
    data_link = claude_dir / "mainframe"
    feedback_link = claude_dir / "skills" / "harness-feedback"
    data_link.symlink_to(ROOT / "workspace" / "runtime")
    feedback_link.symlink_to(ROOT / "dev" / "skills" / "harness-feedback")

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
    assert (home / ".claude" / "CLAUDE.md").is_symlink()
    assert (home / ".claude" / "skills" / "mainframe").is_symlink()
    assert (home / ".claude" / "agents" / "mainframe").is_symlink()

    removed, _ = _run_installer("--claude", "--uninstall", home=home)
    assert removed.returncode == 0, removed.stderr
    assert helper.is_symlink()
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".claude" / "skills" / "mainframe").exists()
    assert not (home / ".claude" / "agents" / "mainframe").exists()


def test_adapter_owns_claude_artifacts():
    assert (ADAPTER / "install.sh").is_file()
    assert (ADAPTER / "export" / "CLAUDE.md").is_file()
    assert (PLUGIN / ".claude-plugin" / "plugin.json").is_file()
    assert AGENTS.is_dir()
    assert not (PLUGIN / "agents").exists()
    assert not (ROOT / "export").exists()
    assert not (ROOT / "plugin-dist").exists()


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
    assert "otherwise return the exact required map update" in verification
    example = json.loads(
        (skill / "infrastructure.example.json").read_text(encoding="utf-8")
    )
    assert example["schemaVersion"] == 1
    assert example["environments"]["production"]["credentialRefs"]


def test_test_auditor_is_non_implementing_and_ticket_scoped():
    auditor = (AGENTS / "mainframe-test-auditor.md").read_text(encoding="utf-8")
    assert "tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch," in auditor
    assert "current primary documentation" in auditor
    assert "mainframe:testing-strategy" in auditor
    assert "mainframe:ticket" in auditor
    assert 'matcher: "Edit|Write"' in auditor
    assert "test-auditor-write-guard.py" in auditor
    assert "Do not use for routine implementation" in auditor
    assert (AGENTS / "hooks" / "test-auditor-write-guard.py").is_file()


def test_testing_context_preserves_role_boundaries():
    strategy = (PLUGIN / "skills" / "testing-strategy" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized_strategy = " ".join(strategy.split())
    assert "An implementation owner may create, change, and run tests" in normalized_strategy
    assert "An audit-only recipient evaluates the existing evidence" in normalized_strategy

    profiles = {
        "mainframe-python-backend-engineer.md": "mainframe:python-backend-patterns",
        "mainframe-typescript-backend-engineer.md": "mainframe:typescript-backend-patterns",
        "mainframe-react-frontend-engineer.md": "mainframe:react-frontend-patterns",
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

    python_testing = (
        PLUGIN / "skills" / "python-backend-patterns" / "testing.md"
    ).read_text(encoding="utf-8")
    assert "existing test runner" in python_testing
    assert "do not introduce pytest" in python_testing

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
    typescript_runtime = (
        PLUGIN / "skills" / "typescript-backend-patterns" / "runtime.md"
    ).read_text(encoding="utf-8")
    assert "the name is not a\n  safety contract" in typescript_runtime

    react_agent = (AGENTS / "mainframe-react-frontend-engineer.md").read_text(
        encoding="utf-8"
    )
    assert "Bash, Skill, WebSearch" in react_agent
    assert "TodoWrite" not in react_agent
    react_preloads = re.search(
        r"^skills:\n((?:  - .+\n)+)", react_agent, re.MULTILINE
    ).group(1)
    for expected in (
        "mainframe:react-frontend-patterns",
        "mainframe:frontend-design",
        "mainframe:shadcn",
        "mainframe:ticket",
    ):
        assert expected in react_preloads
    for skill_name in ("react-frontend-patterns", "shadcn", "frontend-design"):
        skill_body = (PLUGIN / "skills" / skill_name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "disable-model-invocation: true" not in skill_body
    react_skill = (
        PLUGIN / "skills" / "react-frontend-patterns" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "[testing.md](testing.md)" in react_skill
    assert "does not mandate FSD" in react_skill
    assert "concrete adjacent observation" in react_agent
    assert "without investigating it" in react_agent
    assert "verified out-of-scope defects" not in react_skill

    design_skill = (PLUGIN / "skills" / "frontend-design" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for route in ("modes/operate.md", "modes/persuade.md", "modes/read.md", "modes/experience.md"):
        assert route in design_skill
    assert "quality/flows-and-feedback.md" in design_skill

    shadcn_skill = (PLUGIN / "skills" / "shadcn" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "scripts/inspect-ui.mjs" in shadcn_skill
    assert '"shadcn": false' in shadcn_skill

    principles = (ROOT / "docs" / "principles.md").read_text(encoding="utf-8")
    assert "`surface-ticket`" not in principles
    assert "`needs-refinement`" not in principles
    for state in (
        "observations",
        "needs-scope-review",
        "needs-decision",
        "ready",
        "needs-verification",
    ):
        assert state in principles


def test_researcher_has_private_methodology_boundary():
    researcher = (AGENTS / "mainframe-researcher.md").read_text(encoding="utf-8")
    assert "tools: Read, WebSearch, WebFetch," in researcher
    assert "Grep" not in researcher and "Glob" not in researcher and "Bash" not in researcher
    assert "skills:" not in researcher
    assert 'matcher: "Read"' in researcher
    assert 'matcher: "WebSearch"' in researcher
    assert 'matcher: "WebFetch"' in researcher
    assert "research-read-guard.py" in researcher
    assert "skills/mainframe/skills/research-method/SKILL.md" in researcher

    method = PLUGIN / "skills" / "research-method"
    body = (method / "SKILL.md").read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in body
    assert "user-invocable: false" in body
    for guide in ("software-documentation.md", "economics.md", "news.md"):
        assert (method / "references" / guide).is_file()


def test_decision_reviewer_reads_private_method_without_false_preload():
    reviewer = (AGENTS / "mainframe-decision-reviewer.md").read_text(
        encoding="utf-8"
    )
    assert "mainframe:severity-calibration" in reviewer
    assert "mainframe:decision-review" not in reviewer
    assert "skills/mainframe/skills/decision-review/SKILL.md" in reviewer
    assert "CLAUDE.md" not in reviewer
    assert "Cap source lookups" not in reviewer

    method = (PLUGIN / "skills" / "decision-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "disable-model-invocation: true" in method
    assert "user-invocable: false" in method
    assert "Triggered via agent frontmatter `skills:` preload" not in method
    assert "Preloaded into" not in method


def test_advisor_is_controlled_read_only_and_replaces_builtin_advisor():
    advisor = (AGENTS / "mainframe-advisor.md").read_text(encoding="utf-8")
    assert "tools: Read, Grep, Glob, WebSearch, WebFetch," in advisor
    assert "Bash" not in advisor and "Write" not in advisor and "Edit" not in advisor
    assert "model: opus" in advisor
    assert "effort: high" in advisor
    assert "background: true" in advisor
    assert "MAINFRAME_ADVISOR_CONTEXT_V1" in advisor
    assert "VERDICT: UNVERIFIABLE" in advisor

    workflow = (PLUGIN / "skills" / "init" / "workflow.md").read_text(
        encoding="utf-8"
    )
    settings = json.loads((ADAPTER / "export" / "settings.json").read_text())
    assert "mainframe-advisor" in workflow
    assert "zero-argument" not in workflow
    assert "built-in" not in workflow
    assert "advisorModel" not in settings


def test_old_general_code_audit_is_not_delivered():
    assert not (PLUGIN / "skills" / "code-audit").exists()

    severity = (PLUGIN / "skills" / "severity-calibration" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(severity.split())
    assert "Ordinary broken functionality is not Critical" in normalized
    assert "confidence" in normalized


def test_marker_quality_is_enforced_by_hooks_not_a_discovery_skill():
    assert not (PLUGIN / "skills" / "no-suppression-markers").exists()
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())
    post = json.dumps(hooks["hooks"]["PostToolUse"])
    stop = json.dumps(hooks["hooks"]["Stop"])
    subagent_stop = json.dumps(hooks["hooks"]["SubagentStop"])
    assert "scan-suppression-markers.py" in post
    assert "stop-gate-suppression-markers.py" in stop
    assert "stop-gate-suppression-markers.py" in subagent_stop


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


def test_secrets_skill_uses_index_without_secret_ownership_drift():
    body = (PLUGIN / "skills" / "secrets-handling" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(body.split())
    assert "shared/credentials/credentials-index.md" in normalized
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


def test_init_skill_is_manual_only():
    skill = PLUGIN / "skills" / "init" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    assert "name: init" in body
    assert "disable-model-invocation: true" in body
    assert "context: fork" not in body


def test_init_replaces_automatic_task_workflow():
    init_dir = PLUGIN / "skills" / "init"
    body = (init_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "[workflow.md](workflow.md)" in body
    assert "[codex-exec.md](codex-exec.md)" in body
    assert (init_dir / "workflow.md").is_file()
    assert (init_dir / "codex-exec.md").is_file()
    assert not (PLUGIN / "skills" / "task-workflow").exists()
    assert not (PLUGIN / "hooks" / "scripts" / "session-posture.py").exists()
    assert not (PLUGIN / "hooks" / "scripts" / "task-workflow-engagement.py").exists()
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "task-workflow" not in hooks
    assert "session-posture" not in hooks


def test_init_separates_bounded_dod_from_complex_review():
    init_dir = PLUGIN / "skills" / "init"
    workflow = (init_dir / "workflow.md").read_text(encoding="utf-8")
    codex = (init_dir / "codex-exec.md").read_text(encoding="utf-8")
    assert "A formal DoD alone does not make a task complex" in workflow
    assert "### Bounded formal route" in workflow
    assert "### Complex route" in workflow
    assert "without invoking `mainframe-decision-reviewer`," in workflow
    assert "These checkpoints are required for the complex route" in workflow
    assert "The bounded route ends after direct proof" in " ".join(workflow.split())
    assert "bounded formal" not in codex
    assert "gpt-5.6-terra" not in codex
    assert "gpt-5.6-sol`, `medium`" in codex
    assert "gpt-5.6-sol`, `xhigh`" in codex


def test_codex_review_isolated_from_user_configuration():
    codex = (
        PLUGIN / "skills" / "init" / "codex-exec.md"
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
    assert "authorizes no other branch, history, or remote operation" in body
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


def test_claude_permissions_expose_only_helper_and_index():
    settings = json.loads((ADAPTER / "export" / "settings.json").read_text())
    assert "minimumVersion" not in settings
    allowed = settings["permissions"]["allow"]
    denied = settings["permissions"]["deny"]
    assert "Bash(secret *)" in allowed
    assert "Read(~/Documents/projects/MAINFRAME/shared/credentials/credentials-index.md)" in allowed
    assert "Read(~/.config/credentials/**)" in denied
    assert "Read(**/secrets/**)" in denied


def test_global_settings_preserve_role_language_and_model_contracts():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings["model"] == "fable"
    assert "language" not in settings
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in settings.get("env", {})
    assert "teammateMode" not in settings


def test_sensitive_git_actions_require_runtime_confirmation():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    allowed = settings["permissions"]["allow"]
    asked = settings["permissions"]["ask"]
    assert "Bash(git add *)" in allowed
    assert "Bash(git commit *)" in allowed
    for command in (
        "git push", "git checkout", "git switch", "git stash", "git pull",
        "git merge", "git rebase", "git reset", "git cherry-pick",
        "git revert",
    ):
        rule = f"Bash({command} *)"
        assert rule in asked
        assert rule not in allowed
    assert "Bash(git commit *--amend*)" in asked
    assert not any("git branch" in rule for rule in asked)
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "git-branch-authority.py" in hooks
    assert '"if": "Bash(git *)"' in hooks
    assert (PLUGIN / "hooks" / "scripts" / "git-branch-authority.py").is_file()


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
        "Bash(secret *)",
        "Bash(git add *)",
        "Bash(git commit *)",
        "Bash(git fetch *)",
    }


def test_recursive_delete_policy_is_owned_by_the_path_hook():
    settings = json.loads(
        (ADAPTER / "export" / "settings.json").read_text(encoding="utf-8")
    )
    assert "Bash(rm -rf *)" not in settings["permissions"]["ask"]
    hooks = (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "path-validation.py" in hooks


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
    assert "Bash(npm publish *)" in asked


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
