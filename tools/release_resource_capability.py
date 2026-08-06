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


MANAGED_FILE_REGISTRY_PATH = "mainframe/file-ownership.json"

# The single root each component may seed managed files into. Narrower on
# purpose than COMPONENT_ROOTS in release_component_roots, which lists every
# root a component may target: pinning the ownership registry to the same root
# it seeds keeps one component's records from claiming another's files.
MANAGED_SEED_ROOTS = {
    "credential-tools": "credentials-config",
    "claude-code": "claude-config",
    "codex": "codex-config",
    "opencode": "opencode-config",
    "antigravity-2": "antigravity-data",
    "zcode-desktop": "zcode-config",
}


def _valid_managed_seed_apply(
    component: str,
    resource: dict[str, Any],
) -> bool:
    root = MANAGED_SEED_ROOTS.get(component)
    ownership = resource.get("file_ownership")
    target = resource["target"]
    return (
        root is not None
        and resource["apply"] == "supported"
        and resource["observation"] == "supported"
        and target.get("root") == root
        and bool(target.get("path"))
        and isinstance(ownership, dict)
        and ownership.get("kind") == "managed-file-registry-v1"
        and ownership.get("registry")
        == {
            "target": {"root": root, "path": MANAGED_FILE_REGISTRY_PATH},
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
