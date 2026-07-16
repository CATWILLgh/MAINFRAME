#!/usr/bin/env python3
"""Hermetic release-index tests for the MAINFRAME release contract."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract
from release_graph import reject_dependency_cycles




def _bundle(root: Path, component: str, target_root: str) -> Path:
    bundle = root / "bundles" / component
    (bundle / "tree").mkdir(parents=True)
    (bundle / "config.json").write_text('{"enabled":true}\n')
    (bundle / "tree/item.txt").write_text(f"{component}\n")
    launcher = bundle / "launcher.sh"
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=[
            {
                "id": f"{component}.launcher",
                "kind": "file",
                "source": "launcher.sh",
                "target": {"root": target_root, "path": "launcher.sh"},
            },
            {
                "id": f"{component}.tree",
                "kind": "tree",
                "source": "tree",
                "target": {"root": target_root, "path": "tree"},
            },
        ],
        resources=[
            {
                "id": f"{component}.configuration",
                "strategy": "json-key-merge",
                "source": "config.json",
                "target": {"root": target_root, "path": "config.json"},
                "observation": "unimplemented",
                "apply": "unimplemented",
            }
        ],
        runtime_profile={"config_root": f"${{{component.upper()}_HOME}}"},
    )
    return bundle

def test_release_index_references_authoritative_manifests_by_digest():
    root = Path(tempfile.mkdtemp())
    alpha = _bundle(root, "claude-code", "claude-config")
    beta = _bundle(root, "codex", "codex-config")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )

    release = release_contract.validate_release(root)

    assert release["release_id"] == "test-release"
    assert [entry["component"] for entry in release["manifests"]] == [
        "claude-code",
        "codex",
    ]
    assert all(set(entry) == {"component", "path", "sha256"} for entry in release["manifests"])

    index = json.loads((root / "release.json").read_text())
    alpha_entry = index["manifests"][0]
    alpha_manifest = root / alpha_entry["path"]
    alpha_manifest.write_text(alpha_manifest.read_text() + "\n")
    try:
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "manifest digest" in str(exc)
    else:
        raise AssertionError("tampered indexed manifest was accepted")


def test_release_validation_decodes_the_exact_indexed_manifest():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "claude-code", "claude-config")
    decoy = bundle / "decoy.json"
    decoy.write_text('{"component":"wrong"}\n')
    manifest_path = bundle / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["payload_files"].append(
        {
            "path": "decoy.json",
            "mode": "0644",
            "size": decoy.stat().st_size,
            "sha256": release_contract._digest(decoy),
        }
    )
    manifest["payload_files"].sort(key=lambda row: row["path"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[manifest_path],
    )
    index_path = root / "release.json"
    index = json.loads(index_path.read_text())
    index["manifests"][0]["path"] = "bundles/claude-code/decoy.json"
    index["manifests"][0]["sha256"] = release_contract._digest(decoy)
    index_path.write_text(json.dumps(index, indent=2) + "\n")

    try:
        release_contract.validate_release(root)
    except ValueError:
        pass
    else:
        raise AssertionError("non-manifest indexed file was accepted")


def test_release_validation_requires_dependency_closure_and_global_target_isolation():
    root = Path(tempfile.mkdtemp())
    alpha = _bundle(root, "credential-tools", "user-bin")
    beta = _bundle(root, "mainframe-cli", "user-bin")
    beta_manifest = json.loads((beta / "bundle.json").read_text())
    beta_manifest["dependencies"] = ["missing"]
    (beta / "bundle.json").write_text(json.dumps(beta_manifest, indent=2) + "\n")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )
    try:
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "unknown dependency" in str(exc)
    else:
        raise AssertionError("missing dependency was accepted")

    beta_manifest["dependencies"] = []
    (beta / "bundle.json").write_text(json.dumps(beta_manifest, indent=2) + "\n")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )
    try:
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("cross-bundle target collision was accepted")


def test_release_validation_rejects_cross_bundle_legacy_target_collision():
    root = Path(tempfile.mkdtemp())
    alpha = _bundle(root, "credential-tools", "user-bin")
    beta = _bundle(root, "mainframe-cli", "user-bin")
    alpha_manifest = json.loads((alpha / "bundle.json").read_text())
    alpha_manifest["install_units"][0]["target"]["path"] = "alpha-only"
    (alpha / "bundle.json").write_text(json.dumps(alpha_manifest, indent=2) + "\n")
    beta_manifest = json.loads((beta / "bundle.json").read_text())
    beta_manifest["legacy_artifacts"] = [
        {
            "target": {"root": "user-bin", "path": "alpha-only"},
            "target_suffixes": ["export/launcher.sh"],
        }
    ]
    (beta / "bundle.json").write_text(json.dumps(beta_manifest, indent=2) + "\n")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )

    try:
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("cross-bundle legacy target collision was accepted")


def test_release_validation_rejects_cross_runtime_dependency():
    root = Path(tempfile.mkdtemp())
    alpha = _bundle(root, "claude-code", "claude-config")
    beta = _bundle(root, "opencode", "opencode-config")
    manifest_path = beta / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dependencies"] = ["claude-code"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    release_contract.write_release_index(
        root,
        release_id="test-release",
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )

    try:
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "cannot depend" in str(exc)
    else:
        raise AssertionError("cross-runtime dependency was accepted")


def test_dependency_graph_rejects_cycle_defense_in_depth():
    manifests = [
        {"component": "first", "dependencies": ["second"]},
        {"component": "second", "dependencies": ["first"]},
    ]
    try:
        reject_dependency_cycles(manifests)
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("dependency cycle was accepted")


def test_release_index_rejects_manifest_beneath_symlinked_ancestor():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "claude-code", "claude-config")
    (root / "linked-bundles").symlink_to(root / "bundles")
    redirected = root / "linked-bundles" / "claude-code" / "bundle.json"
    try:
        release_contract.write_release_index(
            root,
            release_id="test-release",
            manifests=[redirected],
        )
    except ValueError as exc:
        assert "symbolic link" in str(exc)
    else:
        raise AssertionError("manifest beneath symlinked ancestor was accepted")


def _run_all():
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
