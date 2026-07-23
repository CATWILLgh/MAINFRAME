"""Validation for bundle resource records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import release_contract_fields as fields
from release_contract_helpers import (
    location,
    require_fields,
    require_object,
    sorted_portable_paths,
    unique_identifier,
)
from release_contract_io import (
    portable_path,
    reject_symlink_segments,
    require_regular_file,
)
from release_json import (
    validate_exact_json_document_source,
    validate_owned_json_source,
    validate_shell_source,
)
from release_resource_capability import valid_apply_declaration


def validate_resources(
    component: str,
    schema_version: int,
    root: Path,
    resources: Any,
    payload_rows: list[dict[str, Any]],
) -> None:
    if not isinstance(resources, list):
        raise ValueError("resources must be a list")
    seen_ids: set[str] = set()
    payload_by_path = {row["path"]: row for row in payload_rows}
    for resource in resources:
        _validate_resource(
            component,
            schema_version,
            root,
            resource,
            payload_by_path,
            seen_ids,
        )
    if [resource["id"] for resource in resources] != sorted(seen_ids):
        raise ValueError("resources must be sorted by id")


def _validate_resource(
    component: str,
    schema_version: int,
    root: Path,
    resource: Any,
    payload_by_path: dict[str, dict[str, Any]],
    seen_ids: set[str],
) -> None:
    require_object(resource, "resource")
    allowed = fields.RESOURCE_REQUIRED_FIELDS | fields.RESOURCE_OPTIONAL_FIELDS
    require_fields(resource, fields.RESOURCE_REQUIRED_FIELDS, allowed, "resource")
    identifier = unique_identifier(resource["id"], seen_ids, "resource")
    strategy = resource["strategy"]
    _validate_strategy(schema_version, resource, identifier)
    has_external_state = "external_state" in resource
    has_source = "source" in resource
    if ((strategy in fields.SOURCE_STRATEGIES) or has_external_state) != has_source:
        raise ValueError(f"resource {identifier!r} has inconsistent source")
    source, source_path = _validate_source(root, resource, identifier, has_source)
    location(resource["target"], f"resource {identifier!r} target")
    observation = resource["observation"]
    _validate_observation(
        component,
        resource,
        identifier,
        strategy,
        observation,
        has_external_state,
    )
    _validate_supported_source(
        root,
        resource,
        identifier,
        strategy,
        observation,
        source,
        source_path,
        payload_by_path,
    )
    if not valid_apply_declaration(component, resource):
        raise ValueError(f"resource {identifier!r} overstates lifecycle support")


def _validate_strategy(
    schema_version: int,
    resource: dict[str, Any],
    identifier: str,
) -> None:
    strategy = resource["strategy"]
    if strategy not in fields.SOURCE_STRATEGIES | fields.SOURCELESS_STRATEGIES:
        raise ValueError(f"resource {identifier!r} has invalid strategy")
    if (
        strategy == fields.EXACT_JSON_DOCUMENT_STRATEGY
        and schema_version != fields.EXACT_JSON_DOCUMENT_SCHEMA_VERSION
    ):
        raise ValueError(
            f"resource {identifier!r} exact JSON document requires schema version 4"
        )
    if strategy == fields.EXACT_JSON_DOCUMENT_STRATEGY and any(
        field in resource
        for field in fields.EXACT_JSON_DOCUMENT_FORBIDDEN_FIELDS
    ):
        raise ValueError(
            f"resource {identifier!r} exact JSON document has foreign claim metadata"
        )
    if strategy == fields.EXACT_JSON_DOCUMENT_STRATEGY and (
        resource["observation"] != "supported"
        or resource["apply"] != "supported"
    ):
        raise ValueError(
            f"resource {identifier!r} exact JSON document requires supported lifecycle"
        )


def _validate_source(
    root: Path,
    resource: dict[str, Any],
    identifier: str,
    has_source: bool,
) -> tuple[str, Path]:
    source = ""
    if has_source:
        source = portable_path(resource["source"], f"resource {identifier!r} source")
        reject_symlink_segments(root, source)
        require_regular_file(root / Path(source), f"resource {identifier!r} source")
    if not sorted_portable_paths(resource.get("legacy_source_suffixes", [])):
        raise ValueError(f"resource {identifier!r} has invalid legacy sources")
    return source, root / Path(source)


def _validate_observation(
    component: str,
    resource: dict[str, Any],
    identifier: str,
    strategy: str,
    observation: Any,
    has_external_state: bool,
) -> None:
    if observation not in {"supported", "unimplemented"}:
        raise ValueError(f"resource {identifier!r} overstates lifecycle support")
    if has_external_state:
        _validate_external_state(component, resource, identifier, observation)
    elif strategy == "manual-action" and observation == "supported":
        raise ValueError(f"resource {identifier!r} overstates lifecycle support")
    if observation == "supported" and strategy not in fields.OBSERVABLE_STRATEGIES:
        if strategy != "json-key-merge" and not has_external_state:
            raise ValueError(f"resource {identifier!r} overstates lifecycle support")


def _validate_external_state(
    component: str,
    resource: dict[str, Any],
    identifier: str,
    observation: str,
) -> None:
    external_state = resource["external_state"]
    label = f"resource {identifier!r} external state"
    require_object(external_state, label)
    require_fields(external_state, {"kind"}, {"kind"}, label)
    if (
        component != "codex"
        or resource["strategy"] != "manual-action"
        or observation != "supported"
        or external_state["kind"] != "codex-hook-trust-v1"
        or resource["target"] != {"root": "codex-config", "path": "hooks.json"}
    ):
        raise ValueError(f"resource {identifier!r} has invalid external state boundary")


def _validate_supported_source(
    root: Path,
    resource: dict[str, Any],
    identifier: str,
    strategy: str,
    observation: str,
    source: str,
    source_path: Path,
    payload_by_path: dict[str, dict[str, Any]],
) -> None:
    if observation == "supported" and strategy in fields.SHELL_STRATEGIES:
        validate_shell_source(source_path, identifier)
    if observation == "supported" and strategy == "json-key-merge":
        expected = _expected_payload(payload_by_path, source, identifier)
        validate_owned_json_source(
            root, source, expected, resource, identifier, parse_location=location
        )
    elif strategy == fields.EXACT_JSON_DOCUMENT_STRATEGY:
        expected = _expected_payload(payload_by_path, source, identifier)
        validate_exact_json_document_source(root, source, expected, identifier)
    elif "ownership" in resource:
        raise ValueError(
            f"resource {identifier!r} ownership requires supported JSON observation"
        )
    elif "owned_json_pointers" in resource:
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers require supported JSON observation"
        )


def _expected_payload(
    payload_by_path: dict[str, dict[str, Any]],
    source: str,
    identifier: str,
) -> dict[str, Any]:
    expected = payload_by_path.get(source)
    if expected is None:
        raise ValueError(f"resource {identifier!r} source is absent from payload inventory")
    return expected
