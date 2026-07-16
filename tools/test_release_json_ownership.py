#!/usr/bin/env python3
"""Hermetic release-wide owned-JSON isolation tests."""

from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import release_contract


def _mcp_catalog(root: Path) -> Path:
    target = root / "metadata/mcp-catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((REPO / "internal/mcpcatalog/catalog.json").read_bytes())
    return target


def _json_resource(
    identifier: str,
    target_root: str,
    *,
    observation: str = "supported",
    pointers: object = ("/owned",),
) -> dict:
    resource = {
        "id": identifier,
        "strategy": "json-key-merge",
        "source": "config.json",
        "target": {"root": target_root, "path": "config.json"},
        "observation": observation,
        "apply": "unimplemented",
    }
    if pointers is not None:
        resource["owned_json_pointers"] = list(pointers)
    return resource


def _owned_map_resource(identifier: str) -> dict:
    return {
        "id": identifier,
        "strategy": "json-key-merge",
        "source": "config.json",
        "target": {"root": "codex-config", "path": "config.json"},
        "observation": "supported",
        "apply": "unimplemented",
        "ownership": {
            "kind": "json-map-entry-registry-v1",
            "map_pointer": "/owned",
            "entry_schema": "decision-rule-v1",
            "registry": {
                "target": {
                    "root": "codex-config",
                    "path": "config.json.mainframe-owned.json",
                },
                "schema_version": 1,
                "entries_pointer": "/actions",
            },
        },
    }


def _write_json_bundle(
    root: Path,
    component: str,
    target_root: str,
    pointers: list[str],
) -> Path:
    bundle = root / "bundles" / component
    bundle.mkdir(parents=True)
    (bundle / "config.json").write_text('{"owned":{"child":true},"peer":true}\n')
    release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=[],
        resources=[_json_resource(component + ".configuration", target_root, pointers=pointers)],
    )
    return bundle


def _write_pointer_bundle(root: Path, component: str, start: int, count: int) -> Path:
    bundle = root / "bundles" / component
    bundle.mkdir(parents=True)
    pointers = [f"/field-{index:04d}" for index in range(start, start + count)]
    document = {pointer[1:]: None for pointer in pointers}
    (bundle / "config.json").write_text(json.dumps(document) + "\n")
    release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=[],
        resources=[_json_resource(component + ".configuration", "user-bin", pointers=pointers)],
    )
    return bundle


def test_release_validation_rejects_overlapping_owned_json_pointers():
    overlap_cases = (
        (["/owned"], ["/owned"]),
        (["/owned"], ["/owned/child"]),
        (["/owned/child"], ["/owned"]),
    )
    for alpha_pointers, beta_pointers in overlap_cases:
        root = Path(tempfile.mkdtemp())
        alpha = _write_json_bundle(
            root, "credential-tools", "user-bin", alpha_pointers
        )
        beta = _write_json_bundle(
            root, "mainframe-cli", "user-bin", beta_pointers
        )
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[alpha / "bundle.json", beta / "bundle.json"],
        )
        try:
            release_contract.validate_release(root)
        except ValueError as exc:
            assert "JSON" in str(exc) and "overlap" in str(exc)
        else:
            raise AssertionError("overlapping JSON ownership was accepted")

    root = Path(tempfile.mkdtemp())
    alpha = _write_json_bundle(root, "credential-tools", "user-bin", ["/owned"])
    beta = _write_json_bundle(root, "mainframe-cli", "user-bin", ["/peer"])
    release_contract.write_release_index(
        root,
        release_id="test-release",
        mcp_catalog=_mcp_catalog(root),
        manifests=[alpha / "bundle.json", beta / "bundle.json"],
    )
    release_contract.validate_release(root)


def test_release_validation_bounds_aggregate_owned_pointers_per_target():
    for second_count, accepted in ((512, True), (513, False)):
        root = Path(tempfile.mkdtemp())
        alpha = _write_pointer_bundle(root, "credential-tools", 0, 512)
        beta = _write_pointer_bundle(root, "mainframe-cli", 512, second_count)
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[alpha / "bundle.json", beta / "bundle.json"],
        )
        try:
            release_contract.validate_release(root)
        except ValueError as exc:
            if accepted:
                raise AssertionError("1024 aggregate pointers were rejected") from exc
            assert "exceeds limit" in str(exc)
        else:
            if not accepted:
                raise AssertionError("1025 aggregate pointers were accepted")


def test_release_validation_isolates_json_resource_and_install_targets():
    target_cases = (
        ("config.json", "config.json", "supported"),
        ("config.json", "config.json/child", "supported"),
        ("config.json/child", "config.json", "unimplemented"),
    )
    for resource_target, install_target, observation in target_cases:
        root = Path(tempfile.mkdtemp())
        bundle = root / "bundles" / "codex"
        bundle.mkdir(parents=True)
        (bundle / "config.json").write_text('{"owned":true}\n')
        (bundle / "unit").write_text("unit\n")
        resource = _json_resource(
            "alpha.configuration",
            "codex-config",
            observation=observation,
            pointers=None if observation == "unimplemented" else ("/owned",),
        )
        resource["target"]["path"] = resource_target
        release_contract.write_bundle_manifest(
            bundle,
            component="codex",
            dependencies=[],
            install_units=[{
                "id": "alpha.unit",
                "kind": "file",
                "source": "unit",
                "target": {"root": "codex-config", "path": install_target},
            }],
            resources=[resource],
        )
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[bundle / "bundle.json"],
        )
        try:
            release_contract.validate_release(root)
        except ValueError as exc:
            assert "overlap" in str(exc)
        else:
            raise AssertionError("JSON resource and install target overlap was accepted")


def test_release_validation_rejects_structurally_incompatible_json_resources():
    cases = (
        {
            "id": "alpha.peer",
            "strategy": "json-key-merge",
            "source": "config.json",
            "target": {"root": "codex-config", "path": "config.json/child"},
            "observation": "supported",
            "apply": "unimplemented",
            "owned_json_pointers": ["/peer"],
        },
        {
            "id": "alpha.seed",
            "strategy": "seed-if-absent",
            "source": "config.json",
            "target": {"root": "codex-config", "path": "config.json"},
            "observation": "supported",
            "apply": "unimplemented",
        },
    )
    for second in cases:
        root = Path(tempfile.mkdtemp())
        bundle = root / "bundles" / "codex"
        bundle.mkdir(parents=True)
        (bundle / "config.json").write_text('{"owned":true,"peer":true}\n')
        release_contract.write_bundle_manifest(
            bundle,
            component="codex",
            dependencies=[],
            install_units=[],
            resources=[_json_resource("alpha.json", "codex-config"), second],
        )
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[bundle / "bundle.json"],
        )
        try:
            release_contract.validate_release(root)
        except ValueError as exc:
            assert "overlap" in str(exc)
        else:
            raise AssertionError("incompatible JSON resource overlap was accepted")


def test_release_validation_allows_directory_resource_above_json_target():
    root = Path(tempfile.mkdtemp())
    bundle = root / "bundles" / "codex"
    bundle.mkdir(parents=True)
    (bundle / "config.json").write_text('{"owned":true}\n')
    json_resource = _json_resource("alpha.json", "codex-config")
    json_resource["target"]["path"] = "managed/config.json"
    release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[
            {
                "id": "alpha.directory",
                "strategy": "ensure-directory",
                "target": {"root": "codex-config", "path": "managed"},
                "observation": "supported",
                "apply": "unimplemented",
            },
            json_resource,
        ],
    )
    release_contract.write_release_index(
        root,
        release_id="test-release",
        mcp_catalog=_mcp_catalog(root),
        manifests=[bundle / "bundle.json"],
    )
    release_contract.validate_release(root)


def test_release_validation_reserves_ownership_registry_and_map_pointer():
    root = Path(tempfile.mkdtemp())
    bundle = root / "bundles" / "codex"
    bundle.mkdir(parents=True)
    (bundle / "config.json").write_text('{"owned":{"action":"deny"}}\n')
    (bundle / "unit").write_text("unit\n")
    owned = _owned_map_resource("alpha.owned")
    static = _json_resource(
        "alpha.static",
        "codex-config",
        pointers=("/owned/action",),
    )
    release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[owned, static],
    )
    try:
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[bundle / "bundle.json"],
        )
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("ownership map pointer was not reserved")

    static["target"]["path"] = "other.json"
    static["strategy"] = "seed-if-absent"
    static.pop("owned_json_pointers")
    static["target"]["path"] = "config.json.mainframe-owned.json"
    release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[owned, static],
    )
    try:
        release_contract.write_release_index(
            root,
            release_id="test-release",
            mcp_catalog=_mcp_catalog(root),
            manifests=[bundle / "bundle.json"],
        )
        release_contract.validate_release(root)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("ownership registry target was not reserved")


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
