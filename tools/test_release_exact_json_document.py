#!/usr/bin/env python3
"""Contract tests for schema-v4 exact JSON documents."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import release_contract
import release_global
import release_mcp_projection


SCHEMA_VERSION = 4
DOCUMENT = {"schema_version": 1, "events": True, "feedback": False}
HOST_REQUIREMENT = {
    "kind": "darwin-application-bundle-v1",
    "bundle_identifier": "com.google.antigravity",
    "exact_versions": ["2.2.1"],
}


def _resource(
    *,
    identifier: str = "codex.diagnostics",
    root: str = "codex-config",
    path: str = "mainframe/diagnostics.json",
) -> dict:
    return {
        "id": identifier,
        "strategy": "exact-json-document",
        "source": "diagnostics.json",
        "target": {"root": root, "path": path},
        "observation": "supported",
        "apply": "supported",
    }


def _write_bundle(
    *,
    bundle_root: Path | None = None,
    component: str = "codex",
    root: str = "codex-config",
    schema_version: int = SCHEMA_VERSION,
    payload: bytes | None = None,
    resources: list[dict] | None = None,
    install_units: list[dict] | None = None,
    mcp_projections: list[dict] | None = None,
    host_requirements: list[dict] | None = None,
) -> tuple[Path, dict]:
    bundle = bundle_root or Path(tempfile.mkdtemp())
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "diagnostics.json").write_bytes(
        payload if payload is not None else json.dumps(DOCUMENT).encode()
    )
    manifest = release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=install_units or [],
        resources=resources
        if resources is not None
        else [_resource(root=root, identifier=f"{component}.diagnostics")],
        mcp_projections=mcp_projections,
        schema_version=schema_version,
        host_requirements=host_requirements,
    )
    return bundle, manifest


def _manifest(resources: list[dict], install_units: list[dict] | None = None) -> dict:
    return {
        "component": "codex",
        "dependencies": [],
        "install_units": install_units or [],
        "legacy_artifacts": [],
        "resources": resources,
        "mcp_projections": [],
    }


def _assert_invalid_write(**kwargs) -> None:
    try:
        _write_bundle(**kwargs)
    except ValueError:
        return
    raise AssertionError(f"invalid exact JSON document was accepted: {kwargs}")


def _assert_global_collision(manifest: dict) -> None:
    try:
        release_global.validate_global_contract(
            [manifest],
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
            unique_identifier=release_contract._unique_identifier,
        )
    except ValueError as exc:
        assert "overlap" in str(exc)
        return
    raise AssertionError("exclusive exact JSON document target overlap was accepted")


def test_schema_four_allows_optional_non_empty_host_requirements():
    bundle, manifest = _write_bundle()
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert "host_requirements" not in manifest
    assert release_contract.validate_bundle(bundle) == manifest

    _, with_requirements = _write_bundle(
        component="antigravity-2",
        root="antigravity-data",
        host_requirements=[HOST_REQUIREMENT],
    )
    assert with_requirements["host_requirements"] == [HOST_REQUIREMENT]
    _assert_invalid_write(
        component="antigravity-2",
        root="antigravity-data",
        host_requirements=[],
    )
    manifest["host_requirements"] = []
    (bundle / "bundle.json").write_text(json.dumps(manifest))
    try:
        release_contract.validate_bundle(bundle)
    except ValueError as exc:
        assert "host requirements" in str(exc)
    else:
        raise AssertionError("schema version 4 accepted empty host requirements")


def test_schema_four_exact_document_validates_through_release_index():
    root = Path(tempfile.mkdtemp())
    bundle, _ = _write_bundle(bundle_root=root / "bundles/codex")
    catalog = root / "metadata/mcp-catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes((REPO / "internal/mcpcatalog/catalog.json").read_bytes())
    index = release_contract.write_release_index(
        root,
        release_id="exact-document-test",
        mcp_catalog=catalog,
        manifests=[bundle / "bundle.json"],
    )
    assert release_contract.validate_release(root) == index


def test_schema_five_preserves_exact_json_document_support():
    bundle, manifest = _write_bundle(schema_version=5)
    assert manifest["schema_version"] == 5
    assert release_contract.validate_bundle(bundle) == manifest


def test_exact_json_document_requires_schema_four_or_newer():
    for schema_version in (2, 3):
        requirements = [HOST_REQUIREMENT] if schema_version == 3 else None
        _assert_invalid_write(
            schema_version=schema_version,
            host_requirements=requirements,
        )


def test_exact_json_document_source_has_strict_bounded_schema():
    invalid_payloads = [
        b"{}",
        b"[]",
        b'{"schema_version":1,"events":true}',
        b'{"schema_version":1,"events":true,"feedback":false,"extra":0}',
        b'{"schema_version":true,"events":true,"feedback":false}',
        b'{"schema_version":2,"events":true,"feedback":false}',
        b'{"schema_version":1,"events":1,"feedback":false}',
        b'{"schema_version":1,"events":true,"feedback":0}',
        b'{"schema_version":1,"events":true,"events":false,"feedback":false}',
        b"\xff",
    ]
    for payload in invalid_payloads:
        _assert_invalid_write(payload=payload)

    oversized = json.dumps(DOCUMENT).encode()
    oversized += b" " * (1024 * 1024 + 1 - len(oversized))
    _assert_invalid_write(payload=oversized)

    boundary = json.dumps(DOCUMENT).encode()
    boundary += b" " * (1024 * 1024 - len(boundary))
    bundle, _ = _write_bundle(payload=boundary)
    release_contract.validate_bundle(bundle)


def test_exact_json_document_rejects_foreign_claim_metadata():
    forbidden = {
        "legacy_source_suffixes": [],
        "owned_json_pointers": ["/events"],
        "ownership": {},
        "external_state": {},
    }
    for field, value in forbidden.items():
        resource = _resource()
        resource[field] = value
        _assert_invalid_write(resources=[resource])


def test_exact_json_document_requires_supported_lifecycle():
    for field in ("observation", "apply"):
        resource = _resource()
        resource[field] = "unimplemented"
        _assert_invalid_write(resources=[resource])


def test_exact_json_document_source_is_inventory_authenticated():
    bundle, _ = _write_bundle()
    (bundle / "diagnostics.json").write_text(
        json.dumps({**DOCUMENT, "events": False})
    )
    try:
        release_contract.validate_bundle(bundle)
    except ValueError as exc:
        assert "integrity" in str(exc) or "inventory" in str(exc)
    else:
        raise AssertionError("changed exact JSON source passed authentication")


def test_exact_json_document_is_an_exclusive_whole_file_claim():
    exact = _resource()
    install = {
        "id": "codex.install",
        "kind": "file",
        "source": "diagnostics.json",
        "target": copy.deepcopy(exact["target"]),
    }
    _assert_global_collision(_manifest([exact], [install]))

    json_claim = {
        "id": "codex.json",
        "strategy": "json-key-merge",
        "source": "diagnostics.json",
        "target": copy.deepcopy(exact["target"]),
        "observation": "supported",
        "apply": "unimplemented",
        "owned_json_pointers": ["/events"],
    }
    _assert_global_collision(_manifest([exact, json_claim]))

    second = copy.deepcopy(exact)
    second["id"] = "codex.second"
    _assert_global_collision(_manifest([exact, second]))

    descendant = {
        "id": "codex.seed",
        "strategy": "seed-if-absent",
        "source": "diagnostics.json",
        "target": {
            "root": "codex-config",
            "path": "mainframe/diagnostics.json/child",
        },
        "observation": "supported",
        "apply": "unimplemented",
    }
    _assert_global_collision(_manifest([exact, descendant]))

    ancestor = copy.deepcopy(descendant)
    ancestor["target"]["path"] = "mainframe"
    _assert_global_collision(_manifest([exact, ancestor]))


def test_exact_json_document_allows_only_ensure_directory_ancestor():
    exact = _resource()
    ancestor = {
        "id": "codex.directory",
        "strategy": "ensure-directory",
        "target": {"root": "codex-config", "path": "mainframe"},
        "observation": "supported",
        "apply": "unimplemented",
    }
    release_global.validate_global_contract(
        [_manifest([ancestor, exact])],
        parse_location=release_contract._location,
        locations_overlap=release_contract._locations_overlap,
        unique_identifier=release_contract._unique_identifier,
    )

    descendant = copy.deepcopy(ancestor)
    descendant["target"]["path"] = "mainframe/diagnostics.json/child"
    _assert_global_collision(_manifest([descendant, exact]))


def test_exact_json_document_collides_with_mcp_projection():
    exact = _resource()
    projection = _codex_projection()
    projection["target"] = copy.deepcopy(exact["target"])
    manifest = {
        **_manifest([exact]),
        "mcp_projections": [projection],
    }
    catalog = json.loads((REPO / "internal/mcpcatalog/catalog.json").read_text())
    try:
        release_mcp_projection.validate_release_projections(
            [manifest],
            catalog,
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
        )
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("exact JSON document and MCP projection overlap was accepted")


def _codex_projection() -> dict:
    return {
        "id": "codex.mcp.context7",
        "codec": "codex-user-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "codex-config", "path": "config.toml"},
        "map_pointer": "/mcp_servers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "codex-config",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }


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
