#!/usr/bin/env python3
"""Hermetic tests for the unlinked OpenCode bundle-v2 projection."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
BUILDER = REPO / "adapters/opencode/build_bundle.py"


def _sandbox() -> Path:
    return Path(tempfile.mkdtemp(prefix="mainframe bundle "))


def _run_builder(output: Path, home: Path, xdg: Path) -> None:
    env = dict(
        os.environ,
        HOME=str(home),
        XDG_CONFIG_HOME=str(xdg),
        PYTHONPATH=os.pathsep.join(path for path in sys.path if path),
    )
    subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--root",
            str(REPO),
            "--output",
            str(output),
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )


def test_cli_build_is_pure_and_projects_an_isolated_bundle():
    sandbox = _sandbox()
    home = sandbox / "home"
    xdg = sandbox / "xdg"
    config = xdg / "opencode/opencode.json"
    claude_config = home / ".claude.json"
    output = sandbox / "bundle-v2"
    config.parent.mkdir(parents=True)
    home.mkdir()
    config.write_text("do not parse or replace")
    claude_config.write_text("do not parse")
    config.chmod(0o640)
    claude_config.chmod(0o600)
    before = {
        config: (config.read_bytes(), stat.S_IMODE(config.stat().st_mode)),
        claude_config: (
            claude_config.read_bytes(),
            stat.S_IMODE(claude_config.stat().st_mode),
        ),
    }

    _run_builder(output, home, xdg)

    for path, (content, mode) in before.items():
        assert path.read_bytes() == content
        assert stat.S_IMODE(path.stat().st_mode) == mode
    assert (output / "AGENTS.md").is_file()
    assert (output / "skills/task-workflow/SKILL.md").is_file()
    assert (output / "agents/decision-reviewer.md").is_file()
    assert (output / "gates/detectors/path-validation.py").is_file()
    assert (output / "plugins/mainframe-gates.js").is_file()
    fragment = json.loads((output / "config-fragment.json").read_text())
    assert fragment["permission"]["bash"]["rm -rf /"] == "deny"
    manifest = json.loads((output / "bundle.json").read_text())
    assert manifest["adapter"] == "opencode"
    assert manifest["configuration"]["mcp_projection"] == (
        "retired_cross_adapter_import"
    )

    projected_paths = [output / "AGENTS.md"]
    projected_paths.extend(
        path
        for root in (
            output / "skills",
            output / "agents",
            output / "gates",
            output / "plugins",
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".md", ".js", ".json", ".py"}
    )
    projected = "\n".join(path.read_text() for path in projected_paths)
    assert "{{mainframe." not in projected
    assert "~/.claude" not in projected
    assert str(home) not in projected
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/plans" in projected


def test_bundled_plugin_blocks_and_writes_only_opencode_telemetry():
    sandbox = _sandbox()
    output = sandbox / "bundle-v2"
    project = sandbox / "project"
    home = sandbox / "home"
    xdg = sandbox / "xdg config"
    project.mkdir()
    home.mkdir()
    _run_builder(output, home, xdg)

    runner = """
import { pathToFileURL } from 'node:url'
const plugin = await import(pathToFileURL(process.argv[1]).href)
const hooks = await plugin.MainframeGates({ directory: process.argv[2] })
let block = ''
try {
  await hooks['tool.execute.before'](
    { tool: 'bash' }, { args: { command: 'rm -rf /' } })
} catch (error) {
  block = String(error.message || error)
}
if (!block) process.exit(2)
const output = { output: '' }
await hooks['tool.execute.after'](
  { tool: 'edit', args: { filePath: process.argv[2] + '/sample.py',
                          oldString: '', newString: 'value = 1' },
    sessionID: 'bundle-test' }, output)
process.stdout.write(block)
"""
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(xdg))
    proc = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            runner,
            str(output / "plugins/mainframe-gates.js"),
            str(project),
        ],
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "outside project" in proc.stdout, (proc.stdout, proc.stderr)
    telemetry = xdg / "opencode/mainframe/telemetry/telemetry.db"
    assert telemetry.is_file(), (telemetry, proc.stdout, proc.stderr)
    with sqlite3.connect(telemetry) as connection:
        sources = connection.execute("SELECT DISTINCT source FROM events").fetchall()
    assert sources == [("opencode",)], sources
    assert not (home / ".claude").exists(), list(home.rglob("*"))


def test_rebuild_does_not_follow_a_managed_directory_symlink():
    sandbox = _sandbox()
    home = sandbox / "home"
    xdg = sandbox / "xdg"
    output = sandbox / "bundle-v2"
    foreign = sandbox / "foreign"
    home.mkdir()
    foreign.mkdir()
    marker = foreign / "marker.txt"
    marker.write_text("foreign")
    output.mkdir()
    (output / "plugins").symlink_to(foreign)

    _run_builder(output, home, xdg)

    assert marker.read_text() == "foreign"
    assert not (output / "plugins").is_symlink()
    assert (output / "plugins/mainframe-gates.js").is_file()


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
