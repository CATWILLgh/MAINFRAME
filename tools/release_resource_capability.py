"""Apply-capability rules for release resources."""
from __future__ import annotations

from typing import Any


def valid_apply_declaration(component: str, resource: dict[str, Any]) -> bool:
    if resource["apply"] == "unimplemented":
        return True
    ownership = resource.get("ownership")
    if resource["apply"] != "supported" or not isinstance(ownership, dict):
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
