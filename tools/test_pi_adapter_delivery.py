#!/usr/bin/env python3
"""Contract tests for the installed MAINFRAME Pi execution adapter."""

import json
import os
import pathlib
import stat
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "install.sh"
ADAPTER = ROOT / "adapters" / "pi"
LAUNCHER = ADAPTER / "bin" / "mainframe-pi"


def _fake_runtime(home: pathlib.Path) -> tuple[dict[str, str], pathlib.Path]:
    fake_bin = home / "fake-bin"
    fake_bin.mkdir(parents=True)
    pi = fake_bin / "pi"
    pi.write_text("#!/bin/sh\necho 'pi 0.84.2'\n", encoding="utf-8")
    pi.chmod(pi.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, HOME=str(home), PATH=f"{fake_bin}:{os.environ['PATH']}")
    return env, fake_bin


def test_root_help_exposes_pi_without_installing_it():
    home = pathlib.Path(tempfile.mkdtemp())
    proc = subprocess.run(
        ["bash", str(INSTALLER)], capture_output=True, text=True, env=dict(os.environ, HOME=str(home))
    )
    assert proc.returncode == 0, proc.stderr
    assert "--pi" in proc.stdout
    assert not (home / ".local" / "bin" / "mainframe-pi").exists()


def test_pi_dry_run_is_adapter_only_and_does_not_install_shared_secrets():
    home = pathlib.Path(tempfile.mkdtemp())
    env, _ = _fake_runtime(home)
    proc = subprocess.run(
        ["bash", str(INSTALLER), "--pi", "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Pi adapter preflight passed" in proc.stdout
    assert "mainframe-pi" in proc.stdout
    assert "shared secrets" not in proc.stdout
    assert not (home / ".local" / "bin" / "mainframe-pi").exists()
    assert not (home / ".config" / "credentials").exists()


def test_pi_dev_dry_run_exposes_telemetry_without_mutating_runtime():
    home = pathlib.Path(tempfile.mkdtemp())
    env, _ = _fake_runtime(home)
    marker = ROOT / "workspace" / "runtime" / "pi" / "telemetry" / "enabled"
    marker_existed = marker.exists()
    proc = subprocess.run(
        ["bash", str(INSTALLER), "--pi", "--dev", "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Pi engineer telemetry" in proc.stdout
    assert marker.exists() is marker_existed


def test_launcher_binds_business_analysis_to_current_project():
    root = pathlib.Path(tempfile.mkdtemp())
    project = root / "project"
    project.mkdir()
    config = root / "profiles.json"
    config.write_text("{}\n", encoding="utf-8")
    captured = root / "arguments.json"
    runner = root / "runner"
    runner.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "json.dump({'cwd': os.getcwd(), 'args': sys.argv[1:]}, open(os.environ['CAPTURED'], 'w'))\n",
        encoding="utf-8",
    )
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR)
    env = dict(
        os.environ,
        MAINFRAME_PI_RUNNER=str(runner),
        MAINFRAME_PI_CONFIG=str(config),
        CAPTURED=str(captured),
    )
    proc = subprocess.run(
        [str(LAUNCHER), "business-analysis", "--initiative", "order-handoff", "--entry", "docs/requirements.md"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(captured.read_text(encoding="utf-8"))
    canonical_project = os.path.realpath(project)
    assert data["cwd"] == canonical_project
    assert data["args"] == [
        str(ADAPTER / "src" / "pilot.ts"),
        "--config",
        str(config),
        "--profile",
        "business-analysis",
        "--project",
        canonical_project,
        "--initiative",
        "order-handoff",
        "--entry",
        "docs/requirements.md",
    ]


def test_launcher_rejects_project_override_and_missing_initiative():
    root = pathlib.Path(tempfile.mkdtemp())
    config = root / "profiles.json"
    config.write_text("{}\n", encoding="utf-8")
    runner = root / "runner"
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ, MAINFRAME_PI_RUNNER=str(runner), MAINFRAME_PI_CONFIG=str(config))

    override = subprocess.run(
        [str(LAUNCHER), "business-analysis", "--initiative", "x", "--project", "/tmp"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert override.returncode == 2
    assert "owned by the installed MAINFRAME Pi launcher" in override.stderr

    missing = subprocess.run(
        [str(LAUNCHER), "business-analysis"], capture_output=True, text=True, env=env
    )
    assert missing.returncode == 2
    assert "requires --initiative" in missing.stderr

    missing_source = subprocess.run(
        [str(LAUNCHER), "business-analysis", "--initiative", "x"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert missing_source.returncode == 2
    assert "requires an explicit --statement, --entry, or --input-file" in missing_source.stderr


def _engineer_launcher_fixture():
    root = pathlib.Path(tempfile.mkdtemp())
    project = root / "project"
    project.mkdir()
    config = root / "profiles.json"
    config.write_text("{}\n", encoding="utf-8")
    captured = root / "arguments.json"
    runner = root / "runner"
    runner.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "json.dump({'cwd': os.getcwd(), 'args': sys.argv[1:]}, open(os.environ['CAPTURED'], 'w'))\n",
        encoding="utf-8",
    )
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR)
    env = dict(
        os.environ,
        MAINFRAME_PI_RUNNER=str(runner),
        MAINFRAME_PI_CONFIG=str(config),
        CAPTURED=str(captured),
    )
    return project, config, captured, env


def test_launcher_compiles_new_request_for_current_worktree():
    project, config, captured, env = _engineer_launcher_fixture()
    proc = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "new", "--request", ".agents/runtime/pi/requests/block.json"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(captured.read_text(encoding="utf-8"))
    canonical_project = os.path.realpath(project)
    assert data["cwd"] == canonical_project
    assert data["args"] == [
        str(ADAPTER / "src" / "engineer-pilot.ts"),
        "--config", str(config),
        "--profile", "engineer-pilot",
        "--project", canonical_project,
        "--mode", "new",
        "--request", ".agents/runtime/pi/requests/block.json",
    ]


def test_launcher_resumes_active_worktree_without_repeating_request():
    project, config, captured, env = _engineer_launcher_fixture()
    canonical_project = os.path.realpath(project)
    resume = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "resume", "--feedback", ".agents/runtime/pi/requests/feedback.json"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert resume.returncode == 0, resume.stderr
    data = json.loads(captured.read_text(encoding="utf-8"))
    assert data["args"] == [
        str(ADAPTER / "src" / "engineer-pilot.ts"),
        "--config", str(config),
        "--profile", "engineer-pilot",
        "--project", canonical_project,
        "--mode", "resume",
        "--feedback", ".agents/runtime/pi/requests/feedback.json",
    ]


def test_launcher_has_no_harness_owned_engineer_commit():
    project, _, _, env = _engineer_launcher_fixture()
    proc = subprocess.run(
        [str(LAUNCHER), "engineer", "commit", "--message", "feat(test): close block"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 2
    assert "Unexpected positional argument: commit" in proc.stderr


def test_launcher_rejects_invalid_engineer_mode_combinations():
    project, _, _, env = _engineer_launcher_fixture()

    bad_mode = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "auto", "--request", "block.json"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert bad_mode.returncode == 2
    assert "requires --mode new or --mode resume" in bad_mode.stderr

    feedback_on_new = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "new", "--request", "block.json", "--feedback", "feedback.json"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert feedback_on_new.returncode == 2
    assert "--feedback requires --mode resume" in feedback_on_new.stderr

    missing_request = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "new"], cwd=project, capture_output=True, text=True, env=env
    )
    assert missing_request.returncode == 2
    assert "requires --request" in missing_request.stderr

    request_on_resume = subprocess.run(
        [str(LAUNCHER), "engineer", "--mode", "resume", "--request", "block.json"],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
    )
    assert request_on_resume.returncode == 2
    assert "does not accept --request" in request_on_resume.stderr


def test_launcher_exposes_help_for_each_profile_without_running_pi():
    for profile in ("business-analysis", "engineer"):
        proc = subprocess.run(
            [str(LAUNCHER), profile, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Usage:" in proc.stdout


def test_adapter_skills_expose_one_bounded_primary_invocation():
    claude = ROOT / "adapters" / "claude-code" / "plugin" / "skills" / "pi-business-analysis" / "SKILL.md"
    codex = ROOT / "adapters" / "codex" / "skills" / "mainframe-pi-business-analysis"
    claude_body = claude.read_text(encoding="utf-8")
    codex_body = (codex / "SKILL.md").read_text(encoding="utf-8")
    metadata = (codex / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for body in (claude_body, codex_body):
        assert "mainframe-pi business-analysis" in body
        assert "current project as the analysis boundary" in body
        assert "Pi never owns user communication or product decisions" not in body
        assert "Keep ownership of user communication and product decisions" in body
        assert "second fresh run" in body
        assert "infer the package from ordinary" in body.replace("\n", " ")
    assert "allow_implicit_invocation: true" in metadata
    assert "mainframe-pi-business-analysis" in (ROOT / "adapters" / "codex" / "install.sh").read_text(encoding="utf-8")
    engineer_claude = ROOT / "adapters" / "claude-code" / "plugin" / "skills" / "pi-engineer" / "SKILL.md"
    engineer_codex = ROOT / "adapters" / "codex" / "skills" / "mainframe-pi-engineer"
    for body in (
        engineer_claude.read_text(encoding="utf-8"),
        (engineer_codex / "SKILL.md").read_text(encoding="utf-8"),
    ):
        assert "mainframe-pi engineer --mode new" in body.replace("\n", " ")
        assert "mainframe-pi engineer --mode resume" in body.replace("\n", " ")
        assert "ready-for-architect-review" in body
        assert "Conventional Commit" in body
    engineer_metadata = (engineer_codex / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "allow_implicit_invocation: true" in engineer_metadata
    assert "mainframe-pi-engineer" in (ROOT / "adapters" / "codex" / "install.sh").read_text(encoding="utf-8")


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
