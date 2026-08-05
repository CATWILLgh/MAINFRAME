"""Packaged local ZCode install, removal, and reinstall assertions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


TreeSnapshot = dict[str, tuple[int, bytes | str | None]]
SnapshotTree = Callable[[Path], TreeSnapshot]
Review = Callable[[Path, Path, dict[str, str], dict], tuple[dict, str]]
Apply = Callable[[Path, Path, dict[str, str], dict, str], object]
Draft = Callable[[dict], dict]


def assert_zcode_lifecycle(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
    review: Review,
    apply: Apply,
    draft: Draft,
) -> None:
    _assert_unmanaged_adapters_coexist(binary, home, sandbox, env, review)
    zcode_home = home.parent / "zcode-home"
    zcode_home.mkdir()
    isolated_env = dict(
        env,
        HOME=str(zcode_home),
        CODEX_HOME=str(zcode_home / ".codex"),
        XDG_CONFIG_HOME=str(zcode_home / ".config"),
        XDG_STATE_HOME=str(zcode_home / ".local/state"),
    )
    desired = _desired(["zcode-desktop"])
    response, _ = review(binary, sandbox, isolated_env, desired)
    assert response["apply"]["command_available"] is True
    assert any(
        change["resource_id"] == "zcode-desktop.hooks"
        for change in response["preview"]["configuration"]["changes"]
    )
    _apply_review(binary, sandbox, isolated_env, desired, response, apply, draft)
    _assert_installed(zcode_home)

    config_path = zcode_home / ".zcode/cli/config.json"
    config = json.loads(config_path.read_text())
    config["foreign_object"] = {}
    config["foreign_array"] = []
    config_path.write_text(json.dumps(config) + "\n")
    before_removal = snapshot_tree(zcode_home)

    empty = _desired([])
    response, _ = review(binary, sandbox, isolated_env, empty)
    assert response["apply"]["command_available"] is True
    _apply_review(binary, sandbox, isolated_env, empty, response, apply, draft)
    _assert_removed_with_foreign_state(zcode_home, before_removal)

    response, _ = review(binary, sandbox, isolated_env, desired)
    assert response["apply"]["command_available"] is True
    _apply_review(binary, sandbox, isolated_env, desired, response, apply, draft)
    _assert_installed(zcode_home)
    before_repeat = snapshot_tree(zcode_home)
    response, _ = review(binary, sandbox, isolated_env, desired)
    assert response["apply"] == {"command_available": False}
    assert snapshot_tree(zcode_home) == before_repeat


def _assert_unmanaged_adapters_coexist(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    review: Review,
) -> None:
    coexist_home = home.parent / "zcode-coexist-home"
    legacy = coexist_home / "legacy"
    legacy.mkdir(parents=True)
    targets = {
        coexist_home / ".claude/CLAUDE.md": legacy / "CLAUDE.md",
        coexist_home / ".claude/credentials-index.md": legacy / "credentials-index.md",
        coexist_home / ".claude/settings.json": legacy / "settings.json",
        coexist_home / ".codex/AGENTS.md": legacy / "codex-AGENTS.md",
        coexist_home / ".config/opencode/AGENTS.md": legacy / "opencode-AGENTS.md",
    }
    for target, source in targets.items():
        source.write_text("legacy user-owned configuration\n")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source)
    coexist_env = dict(
        env,
        HOME=str(coexist_home),
        CODEX_HOME=str(coexist_home / ".codex"),
        XDG_CONFIG_HOME=str(coexist_home / ".config"),
        XDG_STATE_HOME=str(coexist_home / ".local/state"),
    )

    response, _ = review(binary, sandbox, coexist_env, _desired(["zcode-desktop"]))

    assert response["apply"]["command_available"] is True
    component_ids = {
        operation["component_id"]
        for operation in response["preview"]["filesystem"]["operations"]
    }
    assert component_ids == {"credential-tools", "mainframe-cli", "zcode-desktop"}


def _desired(adapters: list[str]) -> dict:
    return {
        "adapters": adapters,
        "mcp": [],
        "diagnostics_policy": "preserve-retained-adapters",
    }


def _apply_review(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
    desired: dict,
    response: dict,
    apply: Apply,
    draft: Draft,
) -> None:
    result = apply(
        binary,
        sandbox,
        env,
        draft(desired),
        response["apply"]["confirmation"],
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert json.loads(result.stdout)["applied"] is True


def _assert_installed(home: Path) -> None:
    root = home / ".zcode"
    assert (root / "AGENTS.md").is_symlink()
    assert (root / "agents/decision-reviewer.md").is_symlink()
    assert (root / "skills/task-workflow").is_symlink()
    assert not (root / "skills/decision-review").exists()
    config = json.loads((root / "cli/config.json").read_text())
    assert config["hooks"]["enabled"] is True
    assert set(config["hooks"]["events"]) == {
        "SessionStart", "PreToolUse", "PostToolUse", "Stop",
    }
    registry = json.loads(
        (root / "mainframe/config-ownership.json").read_text()
    )
    assert registry["schema_version"] == 1
    assert len(registry["claims"]) == 5


def _assert_removed_with_foreign_state(
    home: Path,
    before: TreeSnapshot,
) -> None:
    root = home / ".zcode"
    assert not (root / "AGENTS.md").exists()
    assert not (root / "agents/decision-reviewer.md").exists()
    assert not (root / "skills/task-workflow").exists()
    assert not (root / "mainframe/config-ownership.json").exists()
    config = json.loads((root / "cli/config.json").read_text())
    assert config == {"foreign_object": {}, "foreign_array": []}
    assert ".zcode/cli/config.json" in before
