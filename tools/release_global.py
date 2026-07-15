#!/usr/bin/env python3
"""Release-wide identity, target, dependency, and JSON ownership validation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from release_graph import reject_dependency_cycles
from release_json import (
    MAX_OWNED_JSON_POINTERS,
    json_pointer_tokens,
    token_paths_overlap,
)


Location = tuple[str, str]


def validate_local_target_isolation(
    manifest: dict[str, Any],
    *,
    parse_location: Callable[[Any, str], Location],
    locations_overlap: Callable[[Location, Location], bool],
) -> None:
    targets = [
        parse_location(unit["target"], "install target")
        for unit in manifest["install_units"]
    ]
    targets.extend(
        parse_location(artifact["target"], "legacy target")
        for artifact in manifest["legacy_artifacts"]
    )
    for index, target in enumerate(targets):
        for previous in targets[:index]:
            if locations_overlap(previous, target):
                raise ValueError(
                    f"bundle targets {previous!r} and {target!r} overlap"
                )


def validate_global_contract(
    manifests: list[dict[str, Any]],
    *,
    parse_location: Callable[[Any, str], Location],
    locations_overlap: Callable[[Location, Location], bool],
    unique_identifier: Callable[[Any, set[str], str], str],
) -> None:
    components = {manifest["component"] for manifest in manifests}
    identifiers: set[str] = set()
    targets: list[Location] = []
    for manifest in manifests:
        for dependency in manifest["dependencies"]:
            if dependency not in components:
                raise ValueError(
                    f"component {manifest['component']!r} has unknown dependency {dependency!r}"
                )
        for collection in (manifest["install_units"], manifest["resources"]):
            for item in collection:
                unique_identifier(item["id"], identifiers, "release item")
        target_records = [
            *manifest["install_units"],
            *manifest["legacy_artifacts"],
        ]
        for record in target_records:
            target = parse_location(record["target"], "release target")
            for previous in targets:
                if locations_overlap(previous, target):
                    raise ValueError(
                        f"release targets {previous!r} and {target!r} overlap"
                    )
            targets.append(target)
    _validate_global_json_ownership(
        manifests,
        parse_location=parse_location,
        locations_overlap=locations_overlap,
    )
    reject_dependency_cycles(manifests)


def _validate_global_json_ownership(
    manifests: list[dict[str, Any]],
    *,
    parse_location: Callable[[Any, str], Location],
    locations_overlap: Callable[[Location, Location], bool],
) -> None:
    install_targets = [
        parse_location(unit["target"], "release install target")
        for manifest in manifests
        for unit in manifest["install_units"]
    ]
    ownership: dict[Location, list[tuple[str, ...]]] = {}
    resource_targets = [
        (
            resource["id"],
            resource["strategy"],
            parse_location(resource["target"], "release resource target"),
        )
        for manifest in manifests
        for resource in manifest["resources"]
    ]
    for manifest in manifests:
        for resource in manifest["resources"]:
            if resource["strategy"] != "json-key-merge":
                continue
            target = parse_location(
                resource["target"], "release JSON resource target"
            )
            if any(locations_overlap(target, install) for install in install_targets):
                raise ValueError(
                    f"release JSON resource target {target!r} overlaps install target"
                )
            _reject_resource_overlap(
                resource["id"],
                target,
                resource_targets,
                locations_overlap,
            )
            previous_paths = ownership.setdefault(target, [])
            for pointer in resource.get("owned_json_pointers", []):
                if len(previous_paths) >= MAX_OWNED_JSON_POINTERS:
                    raise ValueError(
                        f"release JSON ownership for target {target!r} exceeds limit"
                    )
                tokens = json_pointer_tokens(pointer, resource["id"])
                if any(
                    token_paths_overlap(tokens, previous)
                    for previous in previous_paths
                ):
                    raise ValueError(
                        f"release JSON ownership for target {target!r} overlaps"
                    )
                previous_paths.append(tokens)


def _reject_resource_overlap(
    identifier: str,
    target: Location,
    resources: list[tuple[str, str, Location]],
    locations_overlap: Callable[[Location, Location], bool],
) -> None:
    for other_id, strategy, other_target in resources:
        if other_id == identifier or strategy == "manual-action":
            continue
        if strategy == "json-key-merge":
            if target != other_target and locations_overlap(target, other_target):
                raise ValueError("release JSON resource targets overlap")
            continue
        if not locations_overlap(target, other_target):
            continue
        if strategy == "ensure-directory" and _location_ancestor(other_target, target):
            continue
        raise ValueError("release JSON target overlaps non-JSON resource target")


def _location_ancestor(parent: Location, child: Location) -> bool:
    return parent[0] == child[0] and child[1].startswith(parent[1] + "/")
