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
from release_json import validate_owned_json_source, validate_shell_source
SCHEMA_VERSION = 1
BUNDLE_KIND = "mainframe-bundle"
RELEASE_KIND = "mainframe-release"
BUNDLE_FIELDS = {
    "schema_version",
    "kind",
    "component",
    "dependencies",
    "install_units",
    "legacy_artifacts",
    "resources",
    "payload_files",
    "runtime_profile",
}
INDEX_FIELDS = {"schema_version", "kind", "release_id", "manifests"}
UNIT_REQUIRED_FIELDS = {"id", "kind", "source", "target"}
UNIT_OPTIONAL_FIELDS = {"legacy_source_suffixes"}
LEGACY_FIELDS = {"target", "target_suffixes"}
RESOURCE_REQUIRED_FIELDS = {"id", "strategy", "target", "observation", "apply"}
RESOURCE_OPTIONAL_FIELDS = {"source", "legacy_source_suffixes", "owned_json_pointers"}
PAYLOAD_FIELDS = {"path", "mode", "size", "sha256"}
ENTRY_FIELDS = {"component", "path", "sha256"}
SOURCE_STRATEGIES = {"json-key-merge", "seed-if-absent", "shell-line", "shell-line-if-present"}
SOURCELESS_STRATEGIES = {"ensure-directory", "manual-action"}
OBSERVABLE_STRATEGIES = {
    "ensure-directory",
    "seed-if-absent",
    "shell-line",
    "shell-line-if-present",
}
SHELL_STRATEGIES = {"shell-line", "shell-line-if-present"}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
ITEM_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$")
ROOT_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def write_bundle_manifest(
    bundle_root: Path,
    *,
    component: str,
    dependencies: list[str],
    install_units: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    legacy_artifacts: list[dict[str, Any]] | None = None,
    runtime_profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate bundle mappings and write their deterministic integrity manifest."""
    root = _real_directory(bundle_root, "bundle root")
    manifest = {
        "schema_version": SCHEMA_VERSION,
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
    }
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
    manifests: list[Path],
) -> dict[str, Any]:
    """Write an index that references authoritative bundle manifests by digest."""
    root = _real_directory(release_root, "release root")
    if not IDENTIFIER.fullmatch(release_id):
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
    index = {
        "schema_version": SCHEMA_VERSION,
        "kind": RELEASE_KIND,
        "release_id": release_id,
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
    return index


def _validate_bundle_document(root: Path, manifest: Any) -> None:
    _require_object(manifest, "bundle manifest")
    _require_fields(manifest, BUNDLE_FIELDS, BUNDLE_FIELDS, "bundle manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported bundle schema version")
    if manifest["kind"] != BUNDLE_KIND:
        raise ValueError("invalid bundle kind")
    component = manifest["component"]
    if not isinstance(component, str) or not IDENTIFIER.fullmatch(component):
        raise ValueError(f"invalid component id {component!r}")
    dependencies = manifest["dependencies"]
    if not _sorted_unique_strings(dependencies, IDENTIFIER):
        raise ValueError("dependencies must be sorted unique component ids")
    profile = manifest["runtime_profile"]
    _require_object(profile, "runtime profile")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in profile.items()):
        raise ValueError("runtime profile values must be strings")
    _validate_units(root, manifest["install_units"])
    _validate_legacy_artifacts(manifest["legacy_artifacts"])
    validate_local_target_isolation(
        manifest,
        parse_location=_location,
        locations_overlap=_locations_overlap,
    )
    _validate_payload_rows(manifest["payload_files"])
    _validate_resources(root, manifest["resources"], manifest["payload_files"])


def _validate_units(root: Path, units: Any) -> None:
    if not isinstance(units, list):
        raise ValueError("install_units must be a list")
    seen_ids: set[str] = set()
    targets: list[tuple[str, str]] = []
    for unit in units:
        _require_object(unit, "install unit")
        _require_fields(
            unit,
            UNIT_REQUIRED_FIELDS,
            UNIT_REQUIRED_FIELDS | UNIT_OPTIONAL_FIELDS,
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
        _require_fields(artifact, LEGACY_FIELDS, LEGACY_FIELDS, "legacy artifact")
        locations.append(_location(artifact["target"], "legacy artifact target"))
        suffixes = artifact["target_suffixes"]
        if not suffixes or not _sorted_portable_paths(suffixes):
            raise ValueError("legacy artifact target_suffixes must be non-empty")
    if locations != sorted(locations):
        raise ValueError("legacy_artifacts must be sorted by target")


def _validate_resources(root: Path, resources: Any, payload_rows: list[dict[str, Any]]) -> None:
    if not isinstance(resources, list):
        raise ValueError("resources must be a list")
    seen_ids: set[str] = set()
    payload_by_path = {row["path"]: row for row in payload_rows}
    for resource in resources:
        _require_object(resource, "resource")
        allowed = RESOURCE_REQUIRED_FIELDS | RESOURCE_OPTIONAL_FIELDS
        _require_fields(resource, RESOURCE_REQUIRED_FIELDS, allowed, "resource")
        identifier = _unique_identifier(resource["id"], seen_ids, "resource")
        strategy = resource["strategy"]
        if strategy not in SOURCE_STRATEGIES | SOURCELESS_STRATEGIES:
            raise ValueError(f"resource {identifier!r} has invalid strategy")
        has_source = "source" in resource
        if (strategy in SOURCE_STRATEGIES) != has_source:
            raise ValueError(f"resource {identifier!r} has inconsistent source")
        if has_source:
            source = _portable_path(resource["source"], f"resource {identifier!r} source")
            _reject_symlink_segments(root, source)
            source_path = root / Path(source)
            _require_regular_file(source_path, f"resource {identifier!r} source")
        if not _sorted_portable_paths(resource.get("legacy_source_suffixes", [])):
            raise ValueError(f"resource {identifier!r} has invalid legacy sources")
        _location(resource["target"], f"resource {identifier!r} target")
        observation = resource["observation"]
        if resource["apply"] != "unimplemented" or observation not in {
            "supported",
            "unimplemented",
        }:
            raise ValueError(f"resource {identifier!r} overstates lifecycle support")
        if observation == "supported" and strategy not in OBSERVABLE_STRATEGIES:
            if strategy != "json-key-merge":
                raise ValueError(f"resource {identifier!r} overstates lifecycle support")
        if observation == "supported" and strategy in SHELL_STRATEGIES:
            validate_shell_source(source_path, identifier)
        if observation == "supported" and strategy == "json-key-merge":
            expected = payload_by_path.get(source)
            if expected is None:
                raise ValueError(f"resource {identifier!r} source is absent from payload inventory")
            validate_owned_json_source(root, source, expected, resource, identifier)
        elif "owned_json_pointers" in resource:
            raise ValueError(
                f"resource {identifier!r} owned_json_pointers require supported JSON observation"
            )
    if [resource["id"] for resource in resources] != sorted(seen_ids):
        raise ValueError("resources must be sorted by id")


def _validate_payload_rows(rows: Any) -> None:
    if not isinstance(rows, list):
        raise ValueError("payload_files must be a list")
    paths = []
    for row in rows:
        _require_object(row, "payload file")
        _require_fields(row, PAYLOAD_FIELDS, PAYLOAD_FIELDS, "payload file")
        paths.append(_portable_path(row["path"], "payload path"))
        if not isinstance(row["mode"], str) or not re.fullmatch(r"0[0-7]{3}", row["mode"]):
            raise ValueError("invalid payload mode")
        if type(row["size"]) is not int or row["size"] < 0:
            raise ValueError("invalid payload size")
        if not isinstance(row["sha256"], str) or not SHA256.fullmatch(row["sha256"]):
            raise ValueError("invalid payload digest")
    if paths != sorted(set(paths)):
        raise ValueError("payload_files must have sorted unique paths")


def _validate_release_document(root: Path, index: Any) -> list[dict[str, Any]]:
    _require_object(index, "release index")
    _require_fields(index, INDEX_FIELDS, INDEX_FIELDS, "release index")
    if type(index["schema_version"]) is not int or index["schema_version"] != SCHEMA_VERSION or index["kind"] != RELEASE_KIND:
        raise ValueError("unsupported release contract")
    if not isinstance(index["release_id"], str) or not IDENTIFIER.fullmatch(index["release_id"]):
        raise ValueError("invalid release id")
    entries = index["manifests"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("release manifests must be a non-empty list")
    components = []
    manifests = []
    for entry in entries:
        _require_object(entry, "release manifest entry")
        _require_fields(entry, ENTRY_FIELDS, ENTRY_FIELDS, "release manifest entry")
        component = entry["component"]
        if not isinstance(component, str) or not IDENTIFIER.fullmatch(component):
            raise ValueError("invalid release component")
        relative = _portable_path(entry["path"], "release manifest path")
        if not isinstance(entry["sha256"], str) or not SHA256.fullmatch(entry["sha256"]):
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
    return manifests


def _location(value: Any, label: str) -> tuple[str, str]:
    _require_object(value, label)
    _require_fields(value, {"root", "path"}, {"root", "path"}, label)
    root = value["root"]
    if not isinstance(root, str) or not ROOT_IDENTIFIER.fullmatch(root):
        raise ValueError(f"{label} has invalid root")
    return root, _portable_path(value["path"], label)


def _locations_overlap(left: tuple[str, str], right: tuple[str, str]) -> bool:
    if left[0] != right[0]:
        return False
    return left[1] == right[1] or left[1].startswith(right[1] + "/") or right[1].startswith(left[1] + "/")


def _unique_identifier(value: Any, seen: set[str], label: str) -> str:
    if not isinstance(value, str) or not ITEM_IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label} id {value!r}")
    if value in seen:
        raise ValueError(f"duplicate {label} id {value!r}")
    seen.add(value)
    return value


def _require_fields(value: dict, required: set[str], allowed: set[str], label: str) -> None:
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise ValueError(f"{label} missing fields {sorted(missing)}")
    if unknown:
        raise ValueError(f"{label} has unknown fields {sorted(unknown)}")


def _require_object(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")


def _sorted_unique_strings(values: Any, pattern: re.Pattern) -> bool:
    return isinstance(values, list) and all(isinstance(item, str) and pattern.fullmatch(item) for item in values) and values == sorted(set(values))


def _sorted_portable_paths(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    try:
        paths = [_portable_path(value, "legacy path") for value in values]
    except ValueError:
        return False
    return paths == sorted(set(paths))
