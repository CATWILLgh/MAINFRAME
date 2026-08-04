#!/usr/bin/env python3
"""Pinned ZCode Desktop compatibility and Phase-0 contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_NAME = "ZCode Desktop"
BUNDLE_IDENTIFIER = "dev.zcode.app"
APP_VERSION = "3.6.5"
APP_BUILD = "3.6.5.4145"
CLI_VERSION = "0.16.1"
CLI_PATH = Path("/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs")

CAPABILITY_STATUSES = frozenset({"stable", "beta", "optional"})
COMPLETION_CLASSES = frozenset({"core-required", "selected-v1.1", "exploratory"})
HOOK_EVENTS = (
    "PermissionRequest",
    "PostToolUse",
    "PostToolUseFailure",
    "PreToolUse",
    "SessionStart",
    "Stop",
    "UserPromptSubmit",
)

_CAPABILITY_FIELDS = frozenset(
    {"status", "scope", "activation", "evidence", "required_for_core"}
)
_OWNERSHIP_FIELDS = frozenset(
    {
        "id",
        "file",
        "claim_type",
        "json_pointer",
        "selector",
        "purpose",
        "lifecycle",
        "activation_class",
        "preservation",
        "uninstall",
    }
)


def _require_exact_fields(value: dict[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"{label} unknown fields={unknown}; missing fields={missing}")


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def validate_capability_contract(contract: dict[str, Any]) -> None:
    _require_exact_fields(
        contract,
        frozenset({"schema_version", "host", "user_roots", "capabilities"}),
        "capability contract",
    )
    if contract["schema_version"] != 1:
        raise ValueError("capability contract schema_version must be 1")
    _validate_host(contract["host"])
    _validate_user_roots(contract["user_roots"])
    capabilities = contract["capabilities"]
    if not isinstance(capabilities, dict) or not capabilities:
        raise ValueError("capabilities must be a non-empty object")
    for identifier, capability in capabilities.items():
        _require_string(identifier, "capability id")
        _validate_capability(identifier, capability)


def _validate_host(host: Any) -> None:
    if not isinstance(host, dict):
        raise ValueError("host must be an object")
    _require_exact_fields(
        host,
        frozenset(
            {"app_name", "app_version", "app_build", "bundle_id", "cli_version", "cli_path"}
        ),
        "host",
    )
    for key, value in host.items():
        _require_string(value, f"host.{key}")


def _validate_user_roots(roots: Any) -> None:
    if not isinstance(roots, list) or not roots:
        raise ValueError("user_roots must be a non-empty list")
    if roots != sorted(set(roots)):
        raise ValueError("user_roots must be sorted and unique")
    for root in roots:
        _require_string(root, "user root")


def _validate_capability(identifier: str, capability: Any) -> None:
    if not isinstance(capability, dict):
        raise ValueError(f"capability {identifier!r} must be an object")
    _require_exact_fields(capability, _CAPABILITY_FIELDS, f"capability {identifier!r}")
    if capability["status"] not in CAPABILITY_STATUSES:
        raise ValueError(f"capability {identifier!r} has unsupported status")
    scope = capability["scope"]
    if isinstance(scope, list):
        if not scope or scope != sorted(set(scope)):
            raise ValueError(f"capability {identifier!r} scope must be sorted and unique")
        for item in scope:
            _require_string(item, f"capability {identifier!r} scope")
    else:
        _require_string(scope, f"capability {identifier!r} scope")
    _require_string(capability["activation"], f"capability {identifier!r} activation")
    _require_string(capability["evidence"], f"capability {identifier!r} evidence")
    if not isinstance(capability["required_for_core"], bool):
        raise ValueError(f"capability {identifier!r} required_for_core must be boolean")


def validate_ownership_manifest(manifest: dict[str, Any]) -> None:
    _require_exact_fields(
        manifest,
        frozenset({"schema_version", "entries"}),
        "ownership manifest",
    )
    if manifest["schema_version"] != 1:
        raise ValueError("ownership manifest schema_version must be 1")
    entries = manifest["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("ownership entries must be a non-empty list")
    identifiers: set[str] = set()
    pointers: set[str] = set()
    for entry in entries:
        _validate_ownership_entry(entry, identifiers, pointers)


def _validate_ownership_entry(
    entry: Any, identifiers: set[str], pointers: set[str]
) -> None:
    if not isinstance(entry, dict):
        raise ValueError("ownership entry must be an object")
    _require_exact_fields(entry, _OWNERSHIP_FIELDS, "ownership entry")
    identifier = _require_string(entry["id"], "ownership id")
    if identifier in identifiers:
        raise ValueError(f"duplicate ownership id {identifier!r}")
    identifiers.add(identifier)
    if entry["file"] != "~/.zcode/cli/config.json":
        raise ValueError("v1 ownership may target only ~/.zcode/cli/config.json")
    pointer = _require_string(entry["json_pointer"], "ownership json_pointer")
    if pointer in {"/hooks", "/hooks/events", "/mcp", "/mcp/servers"} or not pointer.startswith("/"):
        raise ValueError(f"ownership pointer {pointer!r} is too broad")
    if pointer in pointers:
        raise ValueError(f"duplicate ownership pointer {pointer!r}")
    pointers.add(pointer)
    if entry["claim_type"] not in {"scalar", "matching-array-entry", "map-entry"}:
        raise ValueError(f"ownership entry {identifier!r} has unsupported claim_type")
    selector = entry["selector"]
    if selector is not None:
        _require_string(selector, f"ownership entry {identifier!r} selector")
    for field in ("purpose", "lifecycle", "preservation", "uninstall"):
        _require_string(entry[field], f"ownership entry {identifier!r} {field}")
    if entry["activation_class"] not in COMPLETION_CLASSES:
        raise ValueError(f"ownership entry {identifier!r} has invalid activation_class")


def load_contract(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def managed_host_requirements() -> list[dict[str, Any]]:
    return [
        {
            "kind": "darwin-application-bundle-v1",
            "bundle_identifier": BUNDLE_IDENTIFIER,
            "exact_versions": [APP_VERSION],
        }
    ]
