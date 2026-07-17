#!/usr/bin/env python3
"""Typed native-host requirements for versioned release bundles."""
from __future__ import annotations

from typing import Any

from release_contract_helpers import require_fields, require_object


DARWIN_APPLICATION_BUNDLE_V1 = "darwin-application-bundle-v1"
HOST_REQUIREMENT_FIELDS = {"kind", "bundle_identifier", "exact_versions"}


def canonical_host_requirements(requirements: Any) -> list[dict[str, Any]]:
    if not isinstance(requirements, list):
        raise ValueError("host requirements must be a list")
    if not requirements:
        raise ValueError("host requirements must not be empty")
    normalized = [_canonical_host_requirement(item) for item in requirements]
    normalized.sort(key=_requirement_key)
    keys = [_requirement_key(item) for item in normalized]
    if len(keys) != len(set(keys)):
        raise ValueError("host requirements must be unique")
    return normalized


def validate_host_requirements(requirements: Any) -> None:
    normalized = canonical_host_requirements(requirements)
    if requirements != normalized:
        raise ValueError("host requirements must be sorted and canonical")


def _canonical_host_requirement(requirement: Any) -> dict[str, Any]:
    require_object(requirement, "host requirement")
    require_fields(
        requirement,
        HOST_REQUIREMENT_FIELDS,
        HOST_REQUIREMENT_FIELDS,
        "host requirement",
    )
    if requirement["kind"] != DARWIN_APPLICATION_BUNDLE_V1:
        raise ValueError("unsupported host requirement kind")
    identifier = requirement["bundle_identifier"]
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("host bundle identifier must be a non-empty string")
    versions = requirement["exact_versions"]
    if not isinstance(versions, list) or not versions:
        raise ValueError("host exact versions must be a non-empty list")
    if not all(isinstance(version, str) and version.strip() for version in versions):
        raise ValueError("host exact versions must contain non-empty strings")
    if len(versions) != len(set(versions)):
        raise ValueError("host exact versions must be unique")
    return {
        "kind": requirement["kind"],
        "bundle_identifier": identifier,
        "exact_versions": sorted(versions),
    }


def _requirement_key(requirement: dict[str, Any]) -> tuple[str, str]:
    return requirement["kind"], requirement["bundle_identifier"]
