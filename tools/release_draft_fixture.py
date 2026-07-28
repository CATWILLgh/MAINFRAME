"""Hermetic installed-state fixture for packaged draft apply assertions."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
from pathlib import Path


def install_exact_component_closure(
    release: Path,
    home: Path,
    selected: str,
) -> set[Path]:
    manifests = _release_manifests(release)
    closure = _component_closure(manifests, selected)
    roots = {
        "home": home,
        "antigravity-config": home / ".gemini/config",
        "antigravity-data": home / ".gemini/antigravity",
        "opencode-config": home / ".config/opencode",
        "credentials-config": home / ".config/credentials",
        "user-bin": home / ".local/bin",
    }
    claims = []
    targets = set()
    index_payload = (release / "release.json").read_bytes()
    index_digest = hashlib.sha256(index_payload).hexdigest()
    release_id = json.loads(index_payload)["release_id"]
    for component in sorted(closure):
        manifest_path, manifest = manifests[component]
        for unit in manifest["install_units"]:
            if unit.get("feature"):
                continue
            source = manifest_path.parent / unit["source"]
            target_spec = unit["target"]
            target = roots[target_spec["root"]] / target_spec["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=unit["kind"] == "tree")
            targets.add(target)
            claims.append({
                "unit_id": unit["id"],
                "component_id": component,
                "target": target_spec,
                "raw_target": str(source),
                "release_id": release_id,
                "index_sha256": index_digest,
            })
    _write_ownership_registry(home, claims)
    _preseed_unimplemented_resources(manifests, closure, roots)
    return targets


def install_exact_antigravity_base(
    release: Path,
    home: Path,
    secret_name: str,
    secret_value: str,
) -> set[Path]:
    home.mkdir(mode=0o700)
    write_draft_credential(home, secret_name)
    _write_fake_antigravity(home)
    managed = install_exact_component_closure(release, home, "antigravity-2")
    path = home / ".config/credentials/secrets.env"
    path.write_text(f"{secret_name}={secret_value}\n")
    path.chmod(0o600)
    return managed


def write_draft_credential(home: Path, secret_name: str) -> None:
    path = home / ".config/credentials/mainframe/instances.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "kind": "mainframe-credential-instances",
        "instances": [{
            "id": "context7-home",
            "service_id": "context7",
            "name": "Home",
            "purpose": "Personal research",
            "credentials": [{
                "role_id": "api-key",
                "secret": {"backend": "secret-env", "name": secret_name},
            }],
        }],
    }))
    path.chmod(0o600)


def _write_fake_antigravity(home: Path) -> None:
    path = home / "Applications/Antigravity.app/Contents/Info.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "com.google.antigravity",
        "CFBundleShortVersionString": "2.2.1",
    }))


def inode_snapshot(paths: set[Path]) -> dict[Path, int]:
    return {path: path.lstat().st_ino for path in paths}


def _release_manifests(release: Path) -> dict[str, tuple[Path, dict]]:
    index = json.loads((release / "release.json").read_text())
    result = {}
    for entry in index["manifests"]:
        path = release / entry["path"]
        result[entry["component"]] = (path, json.loads(path.read_text()))
    return result


def _component_closure(
    manifests: dict[str, tuple[Path, dict]],
    selected: str,
) -> set[str]:
    closure = set()
    pending = [selected]
    while pending:
        component = pending.pop()
        if component in closure:
            continue
        closure.add(component)
        pending.extend(manifests[component][1]["dependencies"])
    return closure


def _write_ownership_registry(home: Path, claims: list[dict]) -> None:
    state = home / ".local/state/mainframe"
    state.mkdir(parents=True, mode=0o700)
    state.chmod(0o700)
    target = state / "link-ownership.json"
    target.write_text(json.dumps({
        "schema_version": 1,
        "claims": claims,
    }, separators=(",", ":")) + "\n")
    target.chmod(0o600)


def _preseed_unimplemented_resources(
    manifests: dict[str, tuple[Path, dict]],
    closure: set[str],
    roots: dict[str, Path],
) -> None:
    for component in closure:
        manifest_path, manifest = manifests[component]
        for resource in manifest.get("resources", []):
            if resource["apply"] != "unimplemented" or "source" not in resource:
                continue
            target_spec = resource["target"]
            target = roots[target_spec["root"]] / target_spec["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            source = manifest_path.parent / resource["source"]
            if resource["strategy"] == "seed-if-absent":
                target.write_bytes(source.read_bytes())
            elif resource["strategy"] == "shell-line":
                target.write_text(source.read_text())
            elif resource["strategy"] == "shell-line-if-present":
                continue
            target.chmod(0o600)
