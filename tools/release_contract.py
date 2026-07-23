#!/usr/bin/env python3
"""Versioned manifest and integrity contract for MAINFRAME release bundles."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from release_contract_io import (
    digest as _digest,
    payload_inventory as _payload_inventory,
    portable_path as _portable_path,
    read_json as _read_json,
    real_directory as _real_directory,
    reject_symlink_segments as _reject_symlink_segments,
    relative_inside as _relative_inside,
    require_regular_file as _require_regular_file,
    write_json as _write_json,
)
from release_global import validate_global_contract, validate_local_target_isolation
from release_component_roots import validate_component_targets
from release_external_state_contract import validate_external_state_units
from mcp_catalog_contract import catalog_entry, validate_catalog_entry
import release_contract_fields as fields
from release_mcp_projection import (
    validate_manifest_projections,
    validate_release_projections,
)
from release_contract_helpers import (
    location as _location,
    locations_overlap as _locations_overlap,
    require_fields as _require_fields,
    require_object as _require_object,
    sorted_portable_paths as _sorted_portable_paths,
    sorted_unique_strings as _sorted_unique_strings,
    unique_identifier as _unique_identifier,
)
import release_host_requirements as host_contract
from release_resource_contract import validate_resources


BUNDLE_SCHEMA_VERSION = 2
RELEASE_SCHEMA_VERSION = 2
BUNDLE_KIND = "mainframe-bundle"
RELEASE_KIND = "mainframe-release"
SOURCE_STRATEGIES = fields.SOURCE_STRATEGIES


def write_bundle_manifest(
    bundle_root: Path,
    *,
    component: str,
    dependencies: list[str],
    install_units: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    legacy_artifacts: list[dict[str, Any]] | None = None,
    runtime_profile: dict[str, str] | None = None,
    mcp_projections: list[dict[str, Any]] | None = None,
    schema_version: int = BUNDLE_SCHEMA_VERSION,
    host_requirements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate bundle mappings and write their deterministic integrity manifest."""
    root = _real_directory(bundle_root, "bundle root")
    manifest = {
        "schema_version": schema_version,
        "kind": BUNDLE_KIND,
        "component": component,
        "dependencies": sorted(dependencies),
        "install_units": sorted(install_units, key=lambda item: item.get("id", "")),
        "legacy_artifacts": sorted(
            legacy_artifacts or [],
            key=lambda item: (
                item.get("target", {}).get("root", ""),
                item.get("target", {}).get("path", ""),
            ),
        ),
        "resources": sorted(resources, key=lambda item: item.get("id", "")),
        "payload_files": _payload_inventory(root),
        "runtime_profile": dict(sorted((runtime_profile or {}).items())),
        "mcp_projections": sorted(
            mcp_projections or [], key=lambda item: item.get("id", "")
        ),
    }
    if schema_version == fields.HOST_REQUIREMENTS_SCHEMA_VERSION or (
        schema_version == fields.EXACT_JSON_DOCUMENT_SCHEMA_VERSION
        and host_requirements is not None
    ):
        manifest["host_requirements"] = host_contract.canonical_host_requirements(
            host_requirements
        )
    elif host_requirements is not None:
        raise ValueError("host requirements require bundle schema version 3 or 4")
    _validate_bundle_document(root, manifest)
    _write_json(root / "bundle.json", manifest)
    return manifest


def validate_bundle(bundle_root: Path) -> dict[str, Any]:
    """Validate one bundle manifest, payload inventory, and source mappings."""
    root = _real_directory(bundle_root, "bundle root")
    manifest_path = root / "bundle.json"
    _require_regular_file(manifest_path, "bundle manifest")
    manifest = _read_json(manifest_path)
    _validate_bundle_document(root, manifest)
    actual = _payload_inventory(root)
    if manifest["payload_files"] != actual:
        raise ValueError(f"{manifest_path}: payload inventory does not match content")
    return manifest


def write_release_index(
    release_root: Path,
    *,
    release_id: str,
    mcp_catalog: Path,
    manifests: list[Path],
) -> dict[str, Any]:
    """Write an index that references authoritative bundle manifests by digest."""
    root = _real_directory(release_root, "release root")
    if not fields.IDENTIFIER.fullmatch(release_id):
        raise ValueError(f"invalid release id {release_id!r}")
    entries = []
    for manifest_path in manifests:
        relative = _relative_inside(root, manifest_path, "bundle manifest")
        manifest = _read_json(manifest_path)
        _validate_bundle_document(manifest_path.parent, manifest)
        if manifest["payload_files"] != _payload_inventory(manifest_path.parent):
            raise ValueError(f"{manifest_path}: payload inventory does not match content")
        entries.append(
            {
                "component": manifest["component"],
                "path": relative,
                "sha256": _digest(manifest_path),
            }
        )
    entries.sort(key=lambda item: item["component"])
    catalog = catalog_entry(root, mcp_catalog)
    index = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "kind": RELEASE_KIND,
        "release_id": release_id,
        "mcp_catalog": catalog,
        "manifests": entries,
    }
    _validate_release_document(root, index)
    _write_json(root / "release.json", index)
    return index


def validate_release(release_root: Path) -> dict[str, Any]:
    """Validate an indexed release without inferring ownership from directories."""
    root = _real_directory(release_root, "release root")
    index_path = root / "release.json"
    _require_regular_file(index_path, "release index")
    index = _read_json(index_path)
    manifests = _validate_release_document(root, index)
    validate_global_contract(
        manifests,
        parse_location=_location,
        locations_overlap=_locations_overlap,
        unique_identifier=_unique_identifier,
    )
    catalog_path = root / index["mcp_catalog"]["path"]
    validate_release_projections(
        manifests,
        _read_json(catalog_path),
        parse_location=_location,
        locations_overlap=_locations_overlap,
    )
    return index


def _validate_bundle_document(root: Path, manifest: Any) -> None:
    _require_object(manifest, "bundle manifest")
    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version not in fields.BUNDLE_FIELDS:
        raise ValueError("unsupported bundle schema version")
    allowed_fields = fields.BUNDLE_FIELDS[schema_version]
    required_fields = fields.BUNDLE_REQUIRED_FIELDS[schema_version]
    _require_fields(manifest, required_fields, allowed_fields, "bundle manifest")
    if manifest["kind"] != BUNDLE_KIND:
        raise ValueError("invalid bundle kind")
    component = manifest["component"]
    if not isinstance(component, str) or not fields.IDENTIFIER.fullmatch(component):
        raise ValueError(f"invalid component id {component!r}")
    dependencies = manifest["dependencies"]
    if not _sorted_unique_strings(dependencies, fields.IDENTIFIER):
        raise ValueError("dependencies must be sorted unique component ids")
    profile = manifest["runtime_profile"]
    _require_object(profile, "runtime profile")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in profile.items()):
        raise ValueError("runtime profile values must be strings")
    if "host_requirements" in manifest:
        host_contract.validate_host_requirements(manifest["host_requirements"])
    _validate_units(root, manifest["install_units"])
    _validate_legacy_artifacts(manifest["legacy_artifacts"])
    validate_local_target_isolation(
        manifest,
        parse_location=_location,
        locations_overlap=_locations_overlap,
    )
    _validate_payload_rows(manifest["payload_files"])
    validate_resources(
        component,
        schema_version,
        root,
        manifest["resources"],
        manifest["payload_files"],
    )
    validate_external_state_units(manifest)
    validate_component_targets(component, manifest)
    validate_manifest_projections(
        component,
        manifest["mcp_projections"],
        parse_location=_location,
    )


def _validate_units(root: Path, units: Any) -> None:
    if not isinstance(units, list):
        raise ValueError("install_units must be a list")
    seen_ids: set[str] = set()
    targets: list[tuple[str, str]] = []
    for unit in units:
        _require_object(unit, "install unit")
        _require_fields(
            unit,
            fields.UNIT_REQUIRED_FIELDS,
            fields.UNIT_REQUIRED_FIELDS | fields.UNIT_OPTIONAL_FIELDS,
            "install unit",
        )
        identifier = _unique_identifier(unit["id"], seen_ids, "install unit")
        kind = unit["kind"]
        if kind not in {"file", "tree"}:
            raise ValueError(f"install unit {identifier!r} has invalid kind")
        source = _portable_path(unit["source"], f"install unit {identifier!r} source")
        source_path = root / Path(source)
        _reject_symlink_segments(root, source)
        if kind == "file":
            _require_regular_file(source_path, f"install unit {identifier!r} source")
        elif not source_path.is_dir():
            raise ValueError(f"install unit {identifier!r} source is not a directory")
        target = _location(unit["target"], f"install unit {identifier!r} target")
        suffixes = unit.get("legacy_source_suffixes", [])
        if not _sorted_portable_paths(suffixes):
            raise ValueError(
                f"install unit {identifier!r} has invalid legacy source suffixes"
            )
        for previous in targets:
            if _locations_overlap(previous, target):
                raise ValueError(f"install unit targets {previous!r} and {target!r} overlap")
        targets.append(target)
    if [unit["id"] for unit in units] != sorted(seen_ids):
        raise ValueError("install_units must be sorted by id")


def _validate_legacy_artifacts(artifacts: Any) -> None:
    if not isinstance(artifacts, list):
        raise ValueError("legacy_artifacts must be a list")
    locations = []
    for artifact in artifacts:
        _require_object(artifact, "legacy artifact")
        _require_fields(artifact, fields.LEGACY_FIELDS, fields.LEGACY_FIELDS, "legacy artifact")
        locations.append(_location(artifact["target"], "legacy artifact target"))
        suffixes = artifact["target_suffixes"]
        if not suffixes or not _sorted_portable_paths(suffixes):
            raise ValueError("legacy artifact target_suffixes must be non-empty")
    if locations != sorted(locations):
        raise ValueError("legacy_artifacts must be sorted by target")


def _validate_payload_rows(rows: Any) -> None:
    if not isinstance(rows, list):
        raise ValueError("payload_files must be a list")
    paths = []
    for row in rows:
        _require_object(row, "payload file")
        _require_fields(row, fields.PAYLOAD_FIELDS, fields.PAYLOAD_FIELDS, "payload file")
        paths.append(_portable_path(row["path"], "payload path"))
        if not isinstance(row["mode"], str) or not re.fullmatch(r"0[0-7]{3}", row["mode"]):
            raise ValueError("invalid payload mode")
        if type(row["size"]) is not int or row["size"] < 0:
            raise ValueError("invalid payload size")
        if not isinstance(row["sha256"], str) or not fields.SHA256.fullmatch(row["sha256"]):
            raise ValueError("invalid payload digest")
    if paths != sorted(set(paths)):
        raise ValueError("payload_files must have sorted unique paths")


def _validate_release_document(root: Path, index: Any) -> list[dict[str, Any]]:
    _require_object(index, "release index")
    _require_fields(index, fields.INDEX_FIELDS, fields.INDEX_FIELDS, "release index")
    if (
        type(index["schema_version"]) is not int
        or index["schema_version"] != RELEASE_SCHEMA_VERSION
        or index["kind"] != RELEASE_KIND
    ):
        raise ValueError("unsupported release contract")
    if not isinstance(index["release_id"], str) or not fields.IDENTIFIER.fullmatch(index["release_id"]):
        raise ValueError("invalid release id")
    catalog = validate_catalog_entry(root, index["mcp_catalog"])
    entries = index["manifests"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("release manifests must be a non-empty list")
    components = []
    manifests = []
    for entry in entries:
        _require_object(entry, "release manifest entry")
        _require_fields(entry, fields.ENTRY_FIELDS, fields.ENTRY_FIELDS, "release manifest entry")
        component = entry["component"]
        if not isinstance(component, str) or not fields.IDENTIFIER.fullmatch(component):
            raise ValueError("invalid release component")
        relative = _portable_path(entry["path"], "release manifest path")
        if not isinstance(entry["sha256"], str) or not fields.SHA256.fullmatch(entry["sha256"]):
            raise ValueError("invalid release manifest digest")
        _reject_symlink_segments(root, relative)
        path = root / Path(relative)
        _require_regular_file(path, "indexed bundle manifest")
        if _digest(path) != entry["sha256"]:
            raise ValueError(f"manifest digest mismatch for {relative}")
        manifest = _read_json(path)
        _validate_bundle_document(path.parent, manifest)
        if manifest["payload_files"] != _payload_inventory(path.parent):
            raise ValueError(f"{path}: payload inventory does not match content")
        if manifest["component"] != component:
            raise ValueError(f"indexed component mismatch for {relative}")
        components.append(component)
        manifests.append(manifest)
    if components != sorted(set(components)):
        raise ValueError("release manifests must be sorted with unique components")
    if catalog["path"] in {entry["path"] for entry in entries}:
        raise ValueError("MCP catalog path overlaps a bundle manifest")
    return manifests
