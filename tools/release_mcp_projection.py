#!/usr/bin/env python3
"""Strict adapter-owned MCP projection contract."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from release_contract_helpers import require_fields, require_object
from release_json import json_pointer_tokens, token_paths_overlap


IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$")
CATALOG_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
PROJECTION_FIELDS = {
    "id", "codec", "server", "profile", "target", "map_pointer",
    "entry_key", "registry",
}
REGISTRY_FIELDS = {"target", "schema_version", "entries_pointer"}
CODEC = "opencode-remote-v1"
MAP_POINTER = "/mcp"
REGISTRY_POINTER = "/servers"
CONFIG_TARGET = ("opencode-config", "opencode.json")
REGISTRY_TARGET = (
    "opencode-config",
    "opencode.json.mainframe-mcp.json",
)


def validate_manifest_projections(
    component: str,
    projections: Any,
    *,
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> None:
    if not isinstance(projections, list):
        raise ValueError("mcp_projections must be a list")
    identifiers: list[str] = []
    for projection in projections:
        require_object(projection, "MCP projection")
        require_fields(
            projection,
            PROJECTION_FIELDS,
            PROJECTION_FIELDS,
            "MCP projection",
        )
        _validate_projection(component, projection, parse_location)
        identifiers.append(projection["id"])
    if identifiers != sorted(set(identifiers)):
        raise ValueError("MCP projections must be sorted with unique ids")


def validate_release_projections(
    manifests: list[dict[str, Any]],
    catalog: dict[str, Any],
    *,
    parse_location: Callable[[Any, str], tuple[str, str]],
    locations_overlap: Callable[[tuple[str, str], tuple[str, str]], bool],
) -> None:
    item_ids, claims, protected_targets, install_targets, resource_targets, registries = (
        _release_target_context(manifests, parse_location)
    )
    projection_ids: set[str] = set()
    projection_registries: list[tuple[str, str]] = []
    for manifest in manifests:
        for projection in manifest["mcp_projections"]:
            identifier = projection["id"]
            if identifier in item_ids or identifier in projection_ids:
                raise ValueError(f"duplicate release item {identifier!r}")
            projection_ids.add(identifier)
            desired_entry(projection, manifest["component"], catalog)
            target = parse_location(projection["target"], "MCP projection target")
            if any(locations_overlap(target, item) for item in install_targets):
                raise ValueError("MCP projection overlaps install target")
            if any(locations_overlap(target, item) for item in registries):
                raise ValueError("MCP projection overlaps ownership registry")
            for strategy, resource_target in resource_targets:
                if target == resource_target and strategy == "json-key-merge":
                    continue
                if locations_overlap(target, resource_target):
                    raise ValueError("MCP projection overlaps resource target")
            claim = json_pointer_tokens(
                projection["map_pointer"] + "/" + projection["entry_key"],
                identifier,
            )
            previous = claims.setdefault(target, [])
            if any(token_paths_overlap(claim, item) for item in previous):
                raise ValueError("MCP projection claims overlap")
            previous.append(claim)
            registry = parse_location(
                projection["registry"]["target"],
                "MCP projection registry",
            )
            if any(locations_overlap(registry, item) for item in protected_targets):
                raise ValueError("MCP projection registry overlaps release target")
            if any(
                registry != item and locations_overlap(registry, item)
                for item in projection_registries
            ):
                raise ValueError("MCP projection registries overlap")
            projection_registries.append(registry)


def _release_target_context(
    manifests: list[dict[str, Any]],
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> tuple[
    set[str],
    dict[tuple[str, str], list[tuple[str, ...]]],
    list[tuple[str, str]],
    list[tuple[str, str]],
    list[tuple[str, tuple[str, str]]],
    list[tuple[str, str]],
]:
    item_ids = {
        item["id"]
        for manifest in manifests
        for collection in (manifest["install_units"], manifest["resources"])
        for item in collection
    }
    install_targets = [
        parse_location(unit["target"], "release install target")
        for manifest in manifests
        for unit in manifest["install_units"]
    ]
    resource_targets = [
        (
            resource["strategy"],
            parse_location(resource["target"], "release resource target"),
        )
        for manifest in manifests
        for resource in manifest["resources"]
    ]
    return (
        item_ids,
        _existing_claims(manifests, parse_location),
        _protected_targets(manifests, parse_location),
        install_targets,
        resource_targets,
        [
            parse_location(
                resource["ownership"]["registry"]["target"],
                "ownership registry",
            )
            for manifest in manifests
            for resource in manifest["resources"]
            if "ownership" in resource
        ],
    )


def desired_entry(
    projection: dict[str, Any],
    component: str,
    catalog: dict[str, Any],
) -> dict[str, str]:
    server = next(
        (item for item in catalog["servers"] if item["id"] == projection["server"]),
        None,
    )
    if server is None:
        raise ValueError("MCP projection references unknown server")
    profile = next(
        (item for item in server["profiles"] if item["id"] == projection["profile"]),
        None,
    )
    if profile is None:
        raise ValueError("MCP projection references unknown profile")
    support = next(
        (item for item in profile["compatibility"] if item["adapter"] == component),
        None,
    )
    authentication = profile["authentication"]
    if (
        support is None
        or support["status"] != "supported"
        or profile["transport"] != "streamable-http"
        or authentication != {
            "kind": "none",
            "placement": "none",
            "environment_variable": "",
        }
        or profile.get("service_credential") is not None
        or not profile.get("endpoint")
    ):
        raise ValueError("MCP profile is incompatible with projection codec")
    return {"type": "remote", "url": profile["endpoint"]}


def _validate_projection(
    component: str,
    projection: dict[str, Any],
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> None:
    if (
        component != "opencode"
        or projection["codec"] != CODEC
        or not isinstance(projection["id"], str)
        or not IDENTIFIER.fullmatch(projection["id"])
    ):
        raise ValueError("unsupported MCP projection identity or codec")
    for field in ("server", "profile", "entry_key"):
        if not isinstance(projection[field], str) or not CATALOG_IDENTIFIER.fullmatch(
            projection[field]
        ):
            raise ValueError(f"invalid MCP projection {field}")
    if projection["entry_key"] != projection["server"]:
        raise ValueError("MCP projection entry key must match server")
    if projection["map_pointer"] != MAP_POINTER:
        raise ValueError("unsupported MCP projection map pointer")
    require_object(projection["registry"], "MCP projection registry")
    require_fields(
        projection["registry"],
        REGISTRY_FIELDS,
        REGISTRY_FIELDS,
        "MCP projection registry",
    )
    registry = projection["registry"]
    if (
        type(registry["schema_version"]) is not int
        or registry["schema_version"] != 1
        or registry["entries_pointer"] != REGISTRY_POINTER
    ):
        raise ValueError("unsupported MCP projection registry contract")
    target = parse_location(projection["target"], "MCP projection target")
    registry_target = parse_location(registry["target"], "MCP projection registry")
    if target != CONFIG_TARGET or registry_target != REGISTRY_TARGET:
        raise ValueError("unsupported MCP projection target")


def _protected_targets(
    manifests: list[dict[str, Any]],
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> list[tuple[str, str]]:
    result = []
    for manifest in manifests:
        result.extend(
            parse_location(item["target"], "release target")
            for collection in (manifest["install_units"], manifest["resources"])
            for item in collection
        )
        result.extend(
            parse_location(resource["ownership"]["registry"]["target"], "ownership registry")
            for resource in manifest["resources"]
            if "ownership" in resource
        )
        result.extend(
            parse_location(projection["target"], "MCP projection target")
            for projection in manifest["mcp_projections"]
        )
    return result


def _existing_claims(
    manifests: list[dict[str, Any]],
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> dict[tuple[str, str], list[tuple[str, ...]]]:
    result: dict[tuple[str, str], list[tuple[str, ...]]] = {}
    for manifest in manifests:
        for resource in manifest["resources"]:
            if resource["strategy"] != "json-key-merge":
                continue
            target = parse_location(resource["target"], "JSON resource target")
            pointers = list(resource.get("owned_json_pointers", []))
            if "ownership" in resource:
                pointers.append(resource["ownership"]["map_pointer"])
            result.setdefault(target, []).extend(
                json_pointer_tokens(pointer, resource["id"])
                for pointer in pointers
            )
    return result
