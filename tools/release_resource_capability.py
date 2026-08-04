"""Apply-capability rules for release resources."""
from __future__ import annotations

from typing import Any

from release_contract_fields import (
    EXACT_JSON_DOCUMENT_FORBIDDEN_FIELDS,
    EXACT_JSON_DOCUMENT_STRATEGY,
)
from release_diagnostics import diagnostics_target


def valid_apply_declaration(component: str, resource: dict[str, Any]) -> bool:
    if resource["strategy"] == "seed-if-absent":
        return (
            resource["apply"] == "unimplemented"
            and "file_ownership" not in resource
        ) or _valid_managed_seed_apply(component, resource)
    if resource["strategy"] == EXACT_JSON_DOCUMENT_STRATEGY:
        return _valid_exact_json_document_apply(component, resource)
    if resource["apply"] == "unimplemented":
        return True
    if resource["apply"] != "supported":
        return False
    json_ownership = resource.get("json_ownership")
    if isinstance(json_ownership, dict):
        registry = json_ownership.get("registry")
        return (
            component == "zcode-desktop"
            and resource["strategy"] == "json-key-merge"
            and resource["observation"] == "supported"
            and resource["target"]["root"] == "zcode-config"
            and isinstance(registry, dict)
            and registry.get("target", {}).get("root") == "zcode-config"
            and registry.get("schema_version") == 1
            and "owned_json_pointers" not in resource
            and "ownership" not in resource
            and "external_state" not in resource
        )
    ownership = resource.get("ownership")
    if not isinstance(ownership, dict):
        return False
    registry = ownership.get("registry")
    return (
        component == "opencode"
        and resource["strategy"] == "json-key-merge"
        and resource["observation"] == "supported"
        and resource["target"]["root"] == "opencode-config"
        and "owned_json_pointers" not in resource
        and ownership.get("kind") == "json-map-entry-registry-v1"
        and ownership.get("entry_schema") == "decision-rule-v1"
        and isinstance(registry, dict)
        and registry.get("target", {}).get("root") == "opencode-config"
        and registry.get("schema_version") == 1
        and registry.get("entries_pointer") == "/actions"
        and "external_state" not in resource
    )


def _valid_managed_seed_apply(
    component: str,
    resource: dict[str, Any],
) -> bool:
    ownership = resource.get("file_ownership")
    return (
        component == "credential-tools"
        and resource["id"] == "credential-tools.secrets-store"
        and resource["apply"] == "supported"
        and resource["observation"] == "supported"
        and resource["target"]
        == {"root": "credentials-config", "path": "secrets.env"}
        and isinstance(ownership, dict)
        and ownership.get("kind") == "managed-file-registry-v1"
        and ownership.get("registry")
        == {
            "target": {
                "root": "credentials-config",
                "path": "mainframe/file-ownership.json",
            },
            "schema_version": 1,
        }
        and "legacy_source_suffixes" not in resource
        and "owned_json_pointers" not in resource
        and "ownership" not in resource
        and "external_state" not in resource
    )


def _valid_exact_json_document_apply(
    component: str,
    resource: dict[str, Any],
) -> bool:
    return (
        resource["apply"] == "supported"
        and resource["target"] == diagnostics_target(component)
        and resource["observation"] == "supported"
        and not any(
            field in resource
            for field in EXACT_JSON_DOCUMENT_FORBIDDEN_FIELDS
        )
    )
