#!/usr/bin/env python3
"""Hermetic bundle-level tests for the MAINFRAME release contract."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract


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


def test_bundle_manifest_records_units_resources_and_payload_integrity():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "credential-tools", "credentials-config")

    manifest = release_contract.validate_bundle(bundle)

    assert manifest["schema_version"] == 6
    assert "host_requirements" not in manifest
    assert manifest["mcp_projections"] == []
    assert manifest["kind"] == "mainframe-bundle"
    assert manifest["component"] == "credential-tools"
    assert [item["id"] for item in manifest["install_units"]] == [
        "credential-tools.launcher",
        "credential-tools.tree",
    ]
    assert manifest["resources"][0]["strategy"] == "json-key-merge"
    payload = {item["path"]: item for item in manifest["payload_files"]}
    assert set(payload) == {"config.json", "launcher.sh", "tree/item.txt"}
    assert payload["launcher.sh"]["mode"] == "0755"
    assert payload["launcher.sh"]["size"] == len("#!/bin/sh\nexit 0\n")
    assert len(payload["launcher.sh"]["sha256"]) == 64


def test_resource_observation_support_matches_strategy_contract():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "seed.txt").write_text("seed\n")
    (bundle / "shell-line").write_text("source ~/.config/example.env\n")

    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[],
        resources=[
            {
                "id": "alpha.directory",
                "strategy": "ensure-directory",
                "target": {"root": "credentials-config", "path": "cache"},
                "observation": "supported",
                "apply": "unimplemented",
            },
            {
                "id": "alpha.seed",
                "strategy": "seed-if-absent",
                "source": "seed.txt",
                "target": {"root": "credentials-config", "path": "seed.txt"},
                "observation": "supported",
                "apply": "unimplemented",
            },
            {
                "id": "alpha.shell",
                "strategy": "shell-line",
                "source": "shell-line",
                "target": {"root": "home", "path": ".zshenv"},
                "observation": "supported",
                "apply": "unimplemented",
            },
        ],
    )

    assert {resource["observation"] for resource in manifest["resources"]} == {
        "supported"
    }

    (bundle / "shell-line").write_text("source ~/.config/example.env")
    release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[],
        resources=[
            {
                "id": "alpha.shell",
                "strategy": "shell-line",
                "source": "shell-line",
                "target": {"root": "home", "path": ".zshenv"},
                "observation": "supported",
                "apply": "unimplemented",
            }
        ],
    )


def test_resource_observation_rejects_unsupported_strategies_and_apply():
    cases = [
        ("json-key-merge", "supported", "unimplemented"),
        ("manual-action", "supported", "unimplemented"),
        ("seed-if-absent", "supported", "supported"),
    ]
    for strategy, observation, apply in cases:
        bundle = Path(tempfile.mkdtemp())
        resource = {
            "id": "alpha.configuration",
            "strategy": strategy,
            "target": {"root": "credentials-config", "path": "config"},
            "observation": observation,
            "apply": apply,
        }
        if strategy in release_contract.SOURCE_STRATEGIES:
            (bundle / "source").write_text("value\n")
            resource["source"] = "source"
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="credential-tools",
                dependencies=[],
                install_units=[],
                resources=[resource],
            )
        except ValueError as exc:
            assert "lifecycle support" in str(exc) or "owned_json_pointers" in str(exc)
        else:
            raise AssertionError(f"unsupported lifecycle was accepted: {strategy}")


def test_supported_shell_resource_requires_one_non_empty_logical_line():
    invalid_payloads = (
        b"",
        b"\n",
        b"   \t\n",
        b"line\r\n",
        b"first\nsecond\n",
        b"\xff",
        b"source\x00env\n",
        "\u001c\n".encode(),
    )
    for payload in invalid_payloads:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "shell-line").write_bytes(payload)
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="credential-tools",
                dependencies=[],
                install_units=[],
                resources=[
                    {
                        "id": "alpha.shell",
                        "strategy": "shell-line-if-present",
                        "source": "shell-line",
                        "target": {"root": "home", "path": ".profile"},
                        "observation": "supported",
                        "apply": "unimplemented",
                    }
                ],
            )
        except ValueError as exc:
            assert "one non-empty logical line" in str(exc)
        else:
            raise AssertionError(f"invalid shell source was accepted: {payload!r}")


def test_bundle_validation_rejects_tampering_and_unknown_fields():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "credential-tools", "credentials-config")
    (bundle / "tree/item.txt").write_text("tampered\n")
    try:
        release_contract.validate_bundle(bundle)
    except ValueError as exc:
        assert "payload inventory" in str(exc)
    else:
        raise AssertionError("tampered payload was accepted")

    bundle = _bundle(
        Path(tempfile.mkdtemp()), "credential-tools", "credentials-config"
    )
    path = bundle / "bundle.json"
    manifest = json.loads(path.read_text())
    manifest["unexpected"] = True
    path.write_text(json.dumps(manifest))
    try:
        release_contract.validate_bundle(bundle)
    except ValueError as exc:
        assert "unknown fields" in str(exc)
    else:
        raise AssertionError("unknown manifest field was accepted")


def test_contract_rejects_boolean_schema_and_payload_size_values():
    root = Path(tempfile.mkdtemp())
    bundle = _bundle(root, "credential-tools", "credentials-config")
    manifest_path = bundle / "bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = True
    manifest["payload_files"][0]["size"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    try:
        release_contract.validate_bundle(bundle)
    except ValueError as exc:
        assert "schema" in str(exc) or "size" in str(exc)
    else:
        raise AssertionError("boolean integer fields were accepted")


def test_bundle_writer_rejects_symlink_payload_and_overlapping_targets():
    root = Path(tempfile.mkdtemp())
    bundle = root / "bundle"
    bundle.mkdir()
    foreign = root / "foreign"
    foreign.write_text("foreign")
    (bundle / "redirect").symlink_to(foreign)
    try:
        release_contract.write_bundle_manifest(
            bundle,
            component="credential-tools",
            dependencies=[],
            install_units=[],
            resources=[],
        )
    except ValueError as exc:
        assert "symbolic link" in str(exc)
    else:
        raise AssertionError("symlink payload was accepted")

    bundle = Path(tempfile.mkdtemp())
    (bundle / "tree/child").mkdir(parents=True)
    (bundle / "tree/child/item").write_text("item")
    try:
        release_contract.write_bundle_manifest(
            bundle,
            component="credential-tools",
            dependencies=[],
            install_units=[
                {
                    "id": "alpha.parent",
                    "kind": "tree",
                    "source": "tree",
                    "target": {"root": "credentials-config", "path": "tree"},
                },
                {
                    "id": "alpha.child",
                    "kind": "tree",
                    "source": "tree/child",
                    "target": {
                        "root": "credentials-config",
                        "path": "tree/child",
                    },
                },
            ],
            resources=[],
        )
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping install targets were accepted")


def test_bundle_manifest_preserves_explicit_legacy_adoption_rules():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "current").write_text("current")
    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[
            {
                "id": "alpha.current",
                "kind": "file",
                "source": "current",
                "target": {"root": "credentials-config", "path": "current"},
                "legacy_source_suffixes": ["dist/alpha/current"],
            }
        ],
        legacy_artifacts=[
            {
                "target": {"root": "credentials-config", "path": "obsolete"},
                "target_suffixes": ["export/obsolete"],
            }
        ],
        resources=[
            {
                "id": "alpha.settings",
                "strategy": "json-key-merge",
                "source": "current",
                "target": {"root": "credentials-config", "path": "settings.json"},
                "legacy_source_suffixes": ["dist/alpha/settings.json"],
                "observation": "unimplemented",
                "apply": "unimplemented",
            }
        ],
    )

    assert manifest["install_units"][0]["legacy_source_suffixes"] == [
        "dist/alpha/current"
    ]
    assert manifest["legacy_artifacts"] == [
        {
            "target": {"root": "credentials-config", "path": "obsolete"},
            "target_suffixes": ["export/obsolete"],
        }
    ]
    assert manifest["resources"][0]["legacy_source_suffixes"] == [
        "dist/alpha/settings.json"
    ]
    assert release_contract.validate_bundle(bundle) == manifest


def test_bundle_rejects_component_targeting_foreign_root():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "payload").write_text("payload\n")
    try:
        release_contract.write_bundle_manifest(
            bundle,
            component="codex",
            dependencies=[],
            install_units=[{
                "id": "codex.payload",
                "kind": "file",
                "source": "payload",
                "target": {"root": "claude-config", "path": "payload"},
            }],
            resources=[],
        )
    except ValueError as exc:
        assert "codex" in str(exc) and "claude-config" in str(exc)
    else:
        raise AssertionError("Codex bundle targeting Claude Code root was accepted")


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
