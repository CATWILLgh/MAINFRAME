"""Packaged CLI assertions for machine draft review and exact application."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Callable

from release_draft_fixture import (
    inode_snapshot,
    install_exact_antigravity_base,
    install_exact_component_closure,
    sentinel_paths,
    write_draft_credential,
    write_draft_secret,
)


TreeSnapshot = dict[str, tuple[int, bytes | str | None]]
SnapshotTree = Callable[[Path], TreeSnapshot]
SECRET_NAME = "CONTEXT7_HOME_KEY"
SECRET_SENTINEL = "mainframe-packaged-secret-sentinel"

def assert_machine_draft_reviews(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    _assert_empty_draft(binary, home, sandbox, env, snapshot_tree)
    _assert_keyed_draft(binary, home, sandbox, env, snapshot_tree)
    _assert_antigravity_keyed_draft(binary, home, sandbox, env, snapshot_tree)


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
    write_draft_credential(home, SECRET_NAME)
    release = binary.parent.parent
    managed = install_exact_component_closure(release, home, "opencode")
    write_draft_secret(home, SECRET_NAME, SECRET_SENTINEL)
    keyed_env = dict(env)
    keyed_env[SECRET_NAME] = SECRET_SENTINEL
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
    response, stdout = _run_review(binary, sandbox, keyed_env, desired)
    assert response["desired"] == desired
    assert response["apply"]["command_available"] is True
    _assert_secret_free(stdout)
    assert snapshot_tree(home) == before
    request = _draft_request(desired)
    confirmation = response["apply"]["confirmation"]
    applied = _run_apply(binary, sandbox, keyed_env, request, confirmation)
    assert applied.returncode == 0, (applied.stdout, applied.stderr)
    assert json.loads(applied.stdout)["applied"] is True
    _assert_secret_free(applied.stdout + applied.stderr)
    _assert_apply_tree_delta(before, snapshot_tree(home))
    _assert_open_code_projection(home)
    first_inodes = inode_snapshot(managed | _managed_configuration_paths(home))
    repeated = _run_review(binary, sandbox, keyed_env, desired)[0]
    assert repeated["apply"]["command_available"] is True
    repeat_before = snapshot_tree(home)
    second = _run_apply(
        binary,
        sandbox,
        keyed_env,
        request,
        repeated["apply"]["confirmation"],
    )
    assert second.returncode == 0, (second.stdout, second.stderr)
    assert json.loads(second.stdout)["applied"] is True
    _assert_secret_free(second.stdout + second.stderr)
    assert snapshot_tree(home) == repeat_before
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
        root / "mainframe/secrets/context7-api-key",
    }


def _assert_secret_free(output: str) -> None:
    assert SECRET_NAME not in output
    assert SECRET_SENTINEL not in output


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
        ".config/opencode/mainframe",
        ".config/opencode/mainframe/secrets",
        ".config/opencode/mainframe/secrets/context7-api-key",
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
            "CONTEXT7_API_KEY": "{file:mainframe/secrets/context7-api-key}",
        },
    }
    assert config["mcp"] == {"context7": expected_context7}
    owned = mcp_registry["servers"]["context7"]
    assert mcp_registry["version"] == 1
    assert owned["format"] == "opencode-file-secret-v1"
    assert owned["profile"] == "remote-api-key"
    assert owned["secret_backend"] == "environment"
    assert owned["secret_reference"] == SECRET_NAME
    assert owned["entry"] == expected_context7
    assert owned["secret_file_sha256"] == hashlib.sha256(
        SECRET_SENTINEL.encode()
    ).hexdigest()
    assert permission_registry == {
        "version": 1,
        "actions": config["permission"],
    }
    assert set(config["permission"]) == {"bash", "read"}
    assert config["permission"]["read"]["~/.config/credentials/**"] == "deny"
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths)
    assert (
        root / "mainframe/secrets/context7-api-key"
    ).read_text() == SECRET_SENTINEL
    assert (root / "mainframe").stat().st_mode & 0o777 == 0o700
    assert (root / "mainframe/secrets").stat().st_mode & 0o777 == 0o700

def _assert_antigravity_keyed_draft(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    snapshot_tree: SnapshotTree,
) -> None:
    release = binary.parent.parent
    home = home.parent / "antigravity-home"
    managed = install_exact_antigravity_base(
        release, home, SECRET_NAME, SECRET_SENTINEL
    )
    isolated_env = dict(
        env, HOME=str(home), CODEX_HOME=str(home / ".codex"),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_STATE_HOME=str(home / ".local/state"),
    )
    before = snapshot_tree(home)
    desired = {
        "adapters": ["antigravity-2"],
        "mcp": [{
            "server_id": "context7",
            "profile_id": "remote-api-key",
            "adapters": ["antigravity-2"],
            "credential_instance_id": "context7-home",
        }],
        "diagnostics_policy": "preserve-retained-adapters",
    }
    response, stdout = _run_review(binary, sandbox, isolated_env, desired)
    assert response["desired"] == desired
    assert len(response["onboarding"]["connections"]) == 1
    assert response["apply"]["command_available"] is True
    assert response["preview"]["configuration"] == {
        "changes": [], "issues": [], "manual_actions": [],
        "notices": [{
            "resource_id": "antigravity-2.live-activation",
            "component_id": "antigravity-2",
            "reason": "manual_action_unverified",
        }],
    }
    _assert_secret_free(stdout)
    assert snapshot_tree(home) == before
    assert sentinel_paths(home, SECRET_SENTINEL.encode()) == {
        ".config/credentials/secrets.env",
    }
    request = _draft_request(desired)
    confirmation = response["apply"]["confirmation"]
    applied = _run_apply(
        binary, sandbox, isolated_env, request, confirmation
    )
    assert applied.returncode == 0, (applied.stdout, applied.stderr)
    assert json.loads(applied.stdout)["applied"] is True
    _assert_secret_free(applied.stdout + applied.stderr)
    _assert_antigravity_delta(before, snapshot_tree(home))
    _assert_antigravity_state(home, release, managed)
    _assert_antigravity_repeat(
        binary, home, sandbox, isolated_env, desired, confirmation, snapshot_tree
    )


def _assert_antigravity_repeat(
    binary: Path,
    home: Path,
    sandbox: Path,
    env: dict[str, str],
    desired: dict,
    previous_confirmation: str,
    snapshot_tree: SnapshotTree,
) -> None:
    first_tree = snapshot_tree(home)
    paths = {home, *home.rglob("*")}
    first_inodes = inode_snapshot(paths)
    repeated, repeat_stdout = _run_review(
        binary, sandbox, env, desired
    )
    assert snapshot_tree(home) == first_tree
    _assert_secret_free(repeat_stdout)
    assert repeated["apply"]["command_available"] is True
    assert repeated["apply"]["confirmation"] != previous_confirmation
    second = _run_apply(
        binary, sandbox, env, _draft_request(desired),
        repeated["apply"]["confirmation"],
    )
    assert second.returncode == 0, (second.stdout, second.stderr)
    _assert_secret_free(second.stdout + second.stderr)
    assert snapshot_tree(home) == first_tree
    assert inode_snapshot(paths) == first_inodes


def _assert_antigravity_delta(before: TreeSnapshot, after: TreeSnapshot) -> None:
    assert set(before) <= set(after)
    assert set(after) - set(before) == {
        ".gemini/antigravity/mainframe",
        ".gemini/antigravity/mainframe/mcp-ownership.json",
        ".gemini/config/mcp_config.json",
        ".local/state/mainframe/transaction.lock",
    }
    assert all(after[path] == state for path, state in before.items())


def _assert_antigravity_state(
    home: Path, release: Path, managed: set[Path],
) -> None:
    config_path = home / ".gemini/config/mcp_config.json"
    registry_path = home / ".gemini/antigravity/mainframe/mcp-ownership.json"
    entry = {
        "headers": {"CONTEXT7_API_KEY": SECRET_SENTINEL},
        "serverUrl": "https://mcp.context7.com/mcp",
    }
    assert json.loads(config_path.read_text()) == {"mcpServers": {"context7": entry}}
    entry_raw = json.dumps(entry, separators=(",", ":"))
    assert json.loads(registry_path.read_text()) == {
        "version": 1, "servers": {"context7": {
            "format": "antigravity-literal-secret-v1",
            "profile": "remote-api-key",
            "secret_backend": "environment",
            "secret_reference": SECRET_NAME,
            "entry_sha256": hashlib.sha256(entry_raw.encode()).hexdigest(),
        }},
    }
    assert sentinel_paths(home, SECRET_SENTINEL.encode()) == {
        ".config/credentials/secrets.env",
        ".gemini/config/mcp_config.json",
    }
    _assert_antigravity_modes_and_ownership(home, release, managed)


def _assert_antigravity_modes_and_ownership(
    home: Path, release: Path, managed: set[Path],
) -> None:
    secure_dirs = {
        home / ".local/state/mainframe",
        home / ".gemini/antigravity/mainframe",
    }
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in secure_dirs)
    secure_files = [
        path for path in home.rglob("*")
        if path.is_file() and not path.is_symlink()
        and "Applications/Antigravity.app" not in path.as_posix()
    ]
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in secure_files)
    registry = json.loads(
        (home / ".local/state/mainframe/link-ownership.json").read_text()
    )
    release_payload = (release / "release.json").read_bytes()
    assert registry["schema_version"] == 1
    assert len(registry["claims"]) == len(managed)
    assert {claim["release_id"] for claim in registry["claims"]} == {
        json.loads(release_payload)["release_id"]
    }
    assert {claim["index_sha256"] for claim in registry["claims"]} == {
        hashlib.sha256(release_payload).hexdigest()
    }
    assert all(set(claim) == {
        "unit_id", "component_id", "target", "raw_target",
        "release_id", "index_sha256",
    } for claim in registry["claims"])
    assert {claim["raw_target"] for claim in registry["claims"]} == {
        str(path.resolve()) for path in managed
    }
    assert not any((home / root).exists() for root in (
        ".claude", ".codex", ".config/opencode",
    ))
