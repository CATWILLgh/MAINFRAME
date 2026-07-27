"""Packaged CLI assertions for read-only machine draft review."""

from __future__ import annotations

import json
import plistlib
import subprocess
from pathlib import Path
from typing import Callable


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
    assert response["apply"] == {"command_available": False}
    assert "CONTEXT7_HOME_KEY" not in stdout
    assert snapshot_tree(home) == before


def _run_review(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
    desired: dict,
) -> tuple[dict, str]:
    reviewed = subprocess.run(
        [str(binary), "draft", "review"],
        input=json.dumps({
            "schema_version": 1,
            "kind": "mainframe-draft",
            "desired": desired,
        }),
        text=True,
        capture_output=True,
        cwd=sandbox,
        env=env,
        check=True,
        timeout=30,
    )
    assert reviewed.stderr == ""
    return json.loads(reviewed.stdout), reviewed.stdout


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
    plist_path.parent.mkdir(parents=True)
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
