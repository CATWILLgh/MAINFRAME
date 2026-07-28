"""Packaged CLI assertions for machine draft review and exact application."""

from __future__ import annotations

import json
import plistlib
import subprocess
from pathlib import Path
from typing import Callable

from release_draft_fixture import (
    inode_snapshot,
    install_exact_opencode_closure,
)


TreeSnapshot = dict[str, tuple[int, bytes | str | None]]
SnapshotTree = Callable[[Path], TreeSnapshot]


def assert_machine_draft_reviews(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    _assert_empty_draft(binary, home, sandbox, env, snapshot_tree)
    _assert_keyed_draft(binary, home, sandbox, env, snapshot_tree)
    _assert_shared_keyed_draft(binary, home, sandbox, env, snapshot_tree)


def _assert_empty_draft(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    before = snapshot_tree(home)
    desired = {
        "adapters": [],
        "mcp": [],
        "diagnostics_policy": "preserve-retained-adapters",
    }
    response, stdout = _run_review(binary, sandbox, env, desired)
    assert response["schema_version"] == 1
    assert response["kind"] == "mainframe-draft-review"
    assert response["state_semantics"] == "complete-desired-state"
    assert response["desired"] == desired
    assert response["apply"] == {"command_available": False}
    assert stdout
    assert snapshot_tree(home) == before


def _assert_keyed_draft(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    _write_draft_credential(home)
    release = binary.parent.parent
    managed = install_exact_opencode_closure(release, home)
    before = snapshot_tree(home)
    desired = {
        "adapters": ["opencode"],
        "mcp": [{
            "server_id": "context7",
            "profile_id": "remote-api-key",
            "adapters": ["opencode"],
            "credential_instance_id": "context7-home",
        }],
        "diagnostics_policy": "preserve-retained-adapters",
    }
    response, stdout = _run_review(binary, sandbox, env, desired)
    assert response["desired"] == desired
    assert response["apply"]["command_available"] is True
    assert "CONTEXT7_HOME_KEY" not in stdout
    assert snapshot_tree(home) == before
    request = _draft_request(desired)
    confirmation = response["apply"]["confirmation"]
    applied = _run_apply(binary, sandbox, env, request, confirmation)
    assert applied.returncode == 0, (applied.stdout, applied.stderr)
    assert json.loads(applied.stdout)["applied"] is True
    assert "CONTEXT7_HOME_KEY" not in applied.stdout + applied.stderr
    _assert_apply_tree_delta(before, snapshot_tree(home))
    _assert_open_code_projection(home)
    first_inodes = inode_snapshot(managed | _managed_configuration_paths(home))
    repeated = _run_review(binary, sandbox, env, desired)[0]
    assert repeated["apply"] == {"command_available": False}
    second = _run_apply(
        binary,
        sandbox,
        env,
        request,
        confirmation,
    )
    assert second.returncode == 1
    assert "CONTEXT7_HOME_KEY" not in second.stdout + second.stderr
    assert inode_snapshot(first_inodes.keys()) == first_inodes


def _run_review(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
    desired: dict,
) -> tuple[dict, str]:
    reviewed = subprocess.run(
        [str(binary), "draft", "review"],
        input=json.dumps(_draft_request(desired)),
        text=True,
        capture_output=True,
        cwd=sandbox,
        env=env,
        check=True,
        timeout=30,
    )
    assert reviewed.stderr == ""
    return json.loads(reviewed.stdout), reviewed.stdout


def _draft_request(desired: dict) -> dict:
    return {
        "schema_version": 1,
        "kind": "mainframe-draft",
        "desired": desired,
    }


def _run_apply(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
    request: dict,
    confirmation: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary), "draft", "apply", "--confirm", confirmation],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=sandbox,
        env=env,
        timeout=30,
    )


def _managed_configuration_paths(home: Path) -> set[Path]:
    root = home / ".config/opencode"
    return {
        root / "opencode.json",
        root / "opencode.json.mainframe-mcp.json",
        root / "opencode.json.mainframe-permissions.json",
    }


def _assert_apply_tree_delta(
    before: TreeSnapshot,
    after: TreeSnapshot,
) -> None:
    assert set(before) <= set(after)
    assert {
        path for path in after if path not in before
    } == {
        ".config/opencode/opencode.json",
        ".config/opencode/opencode.json.mainframe-mcp.json",
        ".config/opencode/opencode.json.mainframe-permissions.json",
        ".local/state/mainframe/transaction.lock",
    }
    assert all(after[path] == state for path, state in before.items())


def _assert_open_code_projection(home: Path) -> None:
    paths = _managed_configuration_paths(home)
    assert all(path.is_file() for path in paths)
    root = home / ".config/opencode"
    config = json.loads((root / "opencode.json").read_text())
    mcp_registry = json.loads(
        (root / "opencode.json.mainframe-mcp.json").read_text()
    )
    permission_registry = json.loads(
        (root / "opencode.json.mainframe-permissions.json").read_text()
    )
    expected_context7 = {
        "type": "remote",
        "url": "https://mcp.context7.com/mcp",
        "headers": {
            "CONTEXT7_API_KEY": "{env:CONTEXT7_HOME_KEY}",
        },
    }
    assert config["mcp"] == {"context7": expected_context7}
    assert mcp_registry == {
        "version": 1,
        "servers": config["mcp"],
    }
    assert permission_registry == {
        "version": 1,
        "actions": config["permission"],
    }
    assert set(config["permission"]) == {"bash", "read"}
    assert config["permission"]["read"]["~/.config/credentials/**"] == "deny"
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths)


def _assert_shared_keyed_draft(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    _write_fake_antigravity(home)
    before = snapshot_tree(home)
    desired = {
        "adapters": ["antigravity-2", "opencode"],
        "mcp": [{
            "server_id": "context7",
            "profile_id": "remote-api-key",
            "adapters": ["antigravity-2", "opencode"],
            "credential_instance_id": "context7-home",
        }],
        "diagnostics_policy": "preserve-retained-adapters",
    }
    response, stdout = _run_review(binary, sandbox, env, desired)
    assert response["desired"] == desired
    assert len(response["onboarding"]["connections"]) == 1
    assert "CONTEXT7_HOME_KEY" not in stdout
    assert snapshot_tree(home) == before


def _write_fake_antigravity(home: Path) -> None:
    plist_path = (
        home / "Applications/Antigravity.app/Contents/Info.plist"
    )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "com.google.antigravity",
        "CFBundleShortVersionString": "2.2.1",
    }))


def _write_draft_credential(home: Path) -> None:
    credential_path = (
        home / ".config/credentials/mainframe/instances.json"
    )
    credential_path.parent.mkdir(parents=True)
    credential_path.write_text(json.dumps({
        "schema_version": 1,
        "kind": "mainframe-credential-instances",
        "instances": [{
            "id": "context7-home",
            "service_id": "context7",
            "name": "Home",
            "purpose": "Personal research",
            "credentials": [{
                "role_id": "api-key",
                "secret": {
                    "backend": "secret-env",
                    "name": "CONTEXT7_HOME_KEY",
                },
            }],
        }],
    }))
    credential_path.chmod(0o600)
