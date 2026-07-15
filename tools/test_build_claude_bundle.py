#!/usr/bin/env python3
"""Hermetic tests for the Claude Code bundle-v2 projection."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters/claude-code"
sys.path.insert(0, str(ADAPTER))

import build_bundle


def _sandbox() -> Path:
    return Path(tempfile.mkdtemp(prefix="mainframe claude bundle "))


def _write(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if executable:
        path.chmod(0o755)


def _fixture_root(sandbox: Path, *, rules: bool = True) -> Path:
    root = sandbox / "root"
    (root / "adapters").mkdir(parents=True)
    shutil.copy2(
        REPO / "adapters/runtime-profiles.json",
        root / "adapters/runtime-profiles.json",
    )
    _write(root / "dist/claude-code/CLAUDE.md", "# Instructions\n")
    _write(root / "dist/claude-code/plugin/SKILL.md", "# Plugin\n")
    _write(
        root / "dist/claude-code/plugin/hooks/run.sh",
        "#!/bin/sh\nexit 0\n",
        executable=True,
    )
    _write(root / "dist/claude-code/output-styles/concise.md", "concise\n")
    _write(root / "dist/claude-code/output-styles/rich/STYLE.md", "rich\n")
    _write(
        root / "dist/claude-code/settings.json",
        json.dumps(
            {
                "model": "sonnet",
                "language": "Russian",
                "permissions": {
                    "allow": ["allow"],
                    "ask": ["ask"],
                    "deny": ["deny"],
                    "defaultMode": "plan",
                },
            },
            indent=2,
        )
        + "\n",
    )
    if rules:
        _write(root / "dist/claude-code/rules/policy.md", "policy\n")
        _write(root / "dist/claude-code/rules/nested/RULE.md", "nested\n")
    _write(
        root / "core/permissions/rules.json",
        json.dumps({"deny": ["deny"], "allow": ["allow"], "ask": ["ask"]}),
    )
    _write(
        root / "core/resources/credentials-index.md",
        "Index: `{{mainframe.config_root}}/credentials-index.md`\n",
    )
    return root


def _unit(
    identifier: str,
    kind: str,
    source: str,
    path: str,
    legacy: list[str],
) -> dict:
    return {
        "id": identifier,
        "kind": kind,
        "source": source,
        "target": {"root": "claude-config", "path": path},
        "legacy_source_suffixes": legacy,
    }


def _expected_units() -> list[dict]:
    return [
        _unit(
            "claude-code.instructions",
            "file",
            "CLAUDE.md",
            "CLAUDE.md",
            ["dist/claude-code/CLAUDE.md", "export/CLAUDE.md"],
        ),
        _unit(
            "claude-code.output-style.concise.md",
            "file",
            "output-styles/concise.md",
            "output-styles/concise.md",
            ["dist/claude-code/output-styles/concise.md"],
        ),
        _unit(
            "claude-code.output-style.rich",
            "tree",
            "output-styles/rich",
            "output-styles/rich",
            ["dist/claude-code/output-styles/rich"],
        ),
        _unit(
            "claude-code.plugin",
            "tree",
            "plugin",
            "skills/mainframe",
            ["dist/claude-code/plugin", "plugin-dist"],
        ),
        _unit(
            "claude-code.rule.nested",
            "tree",
            "rules/nested",
            "rules/nested",
            ["dist/claude-code/rules/nested"],
        ),
        _unit(
            "claude-code.rule.policy.md",
            "file",
            "rules/policy.md",
            "rules/policy.md",
            ["dist/claude-code/rules/policy.md"],
        ),
    ]


def _expected_resources() -> list[dict]:
    return [
        {
            "id": "claude-code.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {"root": "claude-config", "path": "credentials-index.md"},
            "observation": "supported",
            "apply": "unimplemented",
        },
        {
            "id": "claude-code.settings",
            "strategy": "json-key-merge",
            "source": "settings.json",
            "target": {"root": "claude-config", "path": "settings.json"},
            "legacy_source_suffixes": ["dist/claude-code/settings.json"],
            "observation": "unimplemented",
            "apply": "unimplemented",
        },
    ]


def test_manifest_records_exact_units_resources_and_integrity():
    sandbox = _sandbox()
    root = _fixture_root(sandbox)
    output = sandbox / "bundle-v2"

    build_bundle.build(root, output)
    manifest = build_bundle.validate_bundle(output)

    assert manifest["component"] == "claude-code"
    assert manifest["dependencies"] == ["credential-tools", "mainframe-cli"]
    assert manifest["runtime_profile"] == {
        "config_root": "~/.claude",
        "detectors_root": "~/.claude/skills/mainframe/hooks/scripts",
        "plans_root": "~/.claude/plans",
        "skills_root": "~/.claude/skills/mainframe/skills",
    }
    assert manifest["install_units"] == _expected_units()
    assert len(manifest["legacy_artifacts"]) == len(build_bundle.LEGACY_TARGETS)
    assert manifest["legacy_artifacts"][0]["target"]["path"] == (
        "agents/nestjs-backend-engineer.md"
    )
    assert manifest["resources"] == _expected_resources()
    assert (output / "credentials-index.md").read_text() == (
        "Index: `~/.claude/credentials-index.md`\n"
    )
    payload = {item["path"]: item for item in manifest["payload_files"]}
    assert payload["plugin/hooks/run.sh"]["mode"] == "0755"
    assert payload["plugin/hooks/run.sh"]["size"] == len("#!/bin/sh\nexit 0\n")
    assert len(payload["plugin/hooks/run.sh"]["sha256"]) == 64


def test_settings_resource_preserves_complete_claude_configuration():
    sandbox = _sandbox()
    root = _fixture_root(sandbox)
    output = sandbox / "bundle-v2"

    build_bundle.build(root, output)

    assert json.loads((output / "settings.json").read_text()) == {
        "model": "sonnet",
        "language": "Russian",
        "permissions": {
            "allow": ["allow"],
            "ask": ["ask"],
            "deny": ["deny"],
            "defaultMode": "plan",
        },
    }


def test_optional_rules_absence_removes_stale_rules():
    sandbox = _sandbox()
    output = sandbox / "bundle-v2"
    root = _fixture_root(sandbox, rules=False)
    _write(output / "rules/stale.md", "stale\n")

    build_bundle.build(root, output)
    manifest = build_bundle.validate_bundle(output)

    assert not (output / "rules").exists()
    assert all(".rule." not in unit["id"] for unit in manifest["install_units"])


def test_rebuild_removes_stale_payload_and_does_not_follow_symlinks():
    sandbox = _sandbox()
    root = _fixture_root(sandbox)
    output = sandbox / "bundle-v2"
    foreign = sandbox / "foreign"
    foreign.mkdir()
    marker = foreign / "keep.txt"
    marker.write_text("foreign")
    output.mkdir()
    (output / "plugin").symlink_to(foreign, target_is_directory=True)
    _write(output / "obsolete.txt", "stale\n")

    build_bundle.build(root, output)

    assert marker.read_text() == "foreign"
    assert not (output / "plugin").is_symlink()
    assert (output / "plugin/SKILL.md").is_file()
    assert not (output / "obsolete.txt").exists()


def test_cli_build_does_not_read_or_modify_user_state():
    sandbox = _sandbox()
    root = _fixture_root(sandbox)
    output = sandbox / "bundle-v2"
    home = sandbox / "home"
    xdg = sandbox / "xdg"
    settings = home / ".claude/settings.json"
    opencode = xdg / "opencode/opencode.json"
    _write(settings, "do not parse or replace\n")
    _write(opencode, "do not parse or replace\n")
    settings.chmod(0o600)
    opencode.chmod(0o640)
    before = {
        path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (settings, opencode)
    }
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(xdg))

    subprocess.run(
        [
            sys.executable,
            str(ADAPTER / "build_bundle.py"),
            "--root",
            str(root),
            "--output",
            str(output),
        ],
        check=True,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    for path, expected in before.items():
        assert (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) == expected
    assert build_bundle.validate_bundle(output)["component"] == "claude-code"


def _run_all() -> None:
    failures = 0
    tests = [
        (name, function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    for name, function in tests:
        try:
            function()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
