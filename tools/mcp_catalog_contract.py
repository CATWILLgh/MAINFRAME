"""Strict validation for the release-owned MCP catalog."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from release_contract_helpers import require_fields as _require_fields
from release_contract_helpers import require_object as _require_object
from release_contract_io import (
    digest as _digest,
    portable_path as _portable_path,
    read_json as _read_json,
    reject_symlink_segments as _reject_symlink_segments,
    relative_inside as _relative_inside,
    require_regular_file as _require_regular_file,
)


CATALOG_SCHEMA_VERSION = 1
CATALOG_KIND = "mainframe-mcp-catalog"
CATALOG_RELEASE_PATH = "metadata/mcp-catalog.json"
MAX_CATALOG_BYTES = 1 << 20
CATALOG_FIELDS = {"schema_version", "kind", "servers"}
SERVER_FIELDS = {
    "id",
    "name",
    "summary",
    "publisher",
    "homepage_url",
    "documentation_url",
    "repository",
    "license",
    "profiles",
}
REPOSITORY_FIELDS = {"owner", "name", "url"}
PROFILE_REQUIRED_FIELDS = {
    "id",
    "name",
    "transport",
    "authentication",
    "compatibility",
    "evidence",
}
PROFILE_OPTIONAL_FIELDS = {"endpoint", "command", "service_credential"}
AUTHENTICATION_FIELDS = {"kind", "placement", "environment_variable"}
SERVICE_CREDENTIAL_FIELDS = {"kind", "environment_variable"}
COMPATIBILITY_FIELDS = {"adapter", "status", "reason"}
EVIDENCE_FIELDS = {"url", "verified_on"}
ADAPTERS = {"antigravity-2", "claude-code", "codex", "opencode"}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
ENVIRONMENT_VARIABLE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
REPOSITORY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CATALOG_ENTRY_FIELDS = {"path", "sha256"}


def catalog_entry(root: Path, catalog_path: Path) -> dict[str, str]:
    relative = _relative_inside(root, catalog_path, "MCP catalog")
    return validate_catalog_entry(
        root,
        {"path": relative, "sha256": _digest(catalog_path)},
    )


def validate_catalog_entry(root: Path, entry: Any) -> dict[str, str]:
    _require_object(entry, "MCP catalog entry")
    _require_fields(
        entry,
        CATALOG_ENTRY_FIELDS,
        CATALOG_ENTRY_FIELDS,
        "MCP catalog entry",
    )
    relative = _portable_path(entry["path"], "MCP catalog path")
    if relative != CATALOG_RELEASE_PATH:
        raise ValueError(
            f"MCP catalog must use reserved release path {CATALOG_RELEASE_PATH!r}"
        )
    digest = entry["sha256"]
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("invalid MCP catalog digest")
    _reject_symlink_segments(root, relative)
    path = root / Path(relative)
    _require_regular_file(path, "indexed MCP catalog")
    if path.stat().st_size > MAX_CATALOG_BYTES:
        raise ValueError(f"MCP catalog exceeds {MAX_CATALOG_BYTES} bytes")
    if _digest(path) != digest:
        raise ValueError("MCP catalog digest mismatch")
    validate_catalog(_read_json(path))
    return {"path": relative, "sha256": digest}


def validate_catalog(catalog: Any) -> None:
    _object(catalog, "MCP catalog", CATALOG_FIELDS)
    if (
        type(catalog["schema_version"]) is not int
        or catalog["schema_version"] != CATALOG_SCHEMA_VERSION
        or catalog["kind"] != CATALOG_KIND
    ):
        raise ValueError("unsupported MCP catalog contract")
    servers = catalog["servers"]
    if not isinstance(servers, list) or not servers:
        raise ValueError("MCP catalog servers must be a non-empty list")
    for server in servers:
        _validate_server(server)
    _sorted_unique([server["id"] for server in servers], "MCP server ids")


def _validate_server(server: Any) -> None:
    _object(server, "MCP server", SERVER_FIELDS)
    if not IDENTIFIER.fullmatch(server["id"]):
        raise ValueError("invalid MCP server id")
    for field in ("name", "summary", "publisher", "license"):
        if not isinstance(server[field], str) or not server[field]:
            raise ValueError(f"invalid MCP server {field}")
    _https_url(server["homepage_url"], "MCP server homepage")
    _https_url(server["documentation_url"], "MCP server documentation")
    _validate_repository(server["repository"])
    profiles = server["profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("MCP server profiles must be a non-empty list")
    for profile in profiles:
        _validate_profile(profile)
    _sorted_unique([profile["id"] for profile in profiles], "MCP profile ids")


def _validate_repository(repository: Any) -> None:
    _object(repository, "MCP repository", REPOSITORY_FIELDS)
    owner, name = repository["owner"], repository["name"]
    if not isinstance(owner, str) or not REPOSITORY_SEGMENT.fullmatch(owner):
        raise ValueError("invalid MCP repository owner")
    if not isinstance(name, str) or not REPOSITORY_SEGMENT.fullmatch(name):
        raise ValueError("invalid MCP repository name")
    _https_url(repository["url"], "MCP repository")
    parsed = urlparse(repository["url"])
    expected_path = f"/{owner}/{name}".lower()
    if (
        parsed.hostname != "github.com"
        or parsed.path.rstrip("/").lower() != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("MCP repository URL does not match its identity")


def _validate_profile(profile: Any) -> None:
    _object(
        profile,
        "MCP profile",
        PROFILE_REQUIRED_FIELDS,
        PROFILE_REQUIRED_FIELDS | PROFILE_OPTIONAL_FIELDS,
    )
    if (
        not isinstance(profile["id"], str)
        or not IDENTIFIER.fullmatch(profile["id"])
        or not isinstance(profile["name"], str)
        or not profile["name"]
    ):
        raise ValueError("invalid MCP profile identity")
    _validate_transport(profile)
    _validate_authentication(profile["authentication"])
    if "service_credential" in profile:
        _validate_service_credential(profile["service_credential"])
    _validate_compatibility(profile["compatibility"])
    _validate_evidence(profile["evidence"])


def _validate_transport(profile: dict[str, Any]) -> None:
    transport = profile["transport"]
    endpoint = profile.get("endpoint", "")
    command = profile.get("command", [])
    if transport == "streamable-http":
        if command:
            raise ValueError("HTTP MCP profile must not contain a command")
        _https_url(endpoint, "MCP endpoint")
    elif transport == "stdio":
        if endpoint or not _non_empty_strings(command):
            raise ValueError("stdio MCP profile requires only a command")
    else:
        raise ValueError(f"unsupported MCP transport {transport!r}")


def _validate_authentication(authentication: Any) -> None:
    _object(authentication, "MCP authentication", AUTHENTICATION_FIELDS)
    kind = authentication["kind"]
    placement = authentication["placement"]
    variable = authentication["environment_variable"]
    if kind == "none":
        if placement != "none" or variable != "":
            raise ValueError("keyless MCP authentication names a secret")
    elif kind == "api-key":
        if placement != "header" or not ENVIRONMENT_VARIABLE.fullmatch(variable):
            raise ValueError("API-key MCP authentication is incomplete")
    else:
        raise ValueError(f"unsupported MCP authentication {kind!r}")


def _validate_service_credential(credential: Any) -> None:
    _object(credential, "MCP service credential", SERVICE_CREDENTIAL_FIELDS)
    if credential["kind"] != "api-key" or not ENVIRONMENT_VARIABLE.fullmatch(
        credential["environment_variable"]
    ):
        raise ValueError("invalid MCP service credential")


def _validate_compatibility(entries: Any) -> None:
    if not isinstance(entries, list) or len(entries) != len(ADAPTERS):
        raise ValueError("MCP compatibility must classify every adapter")
    for entry in entries:
        _object(entry, "MCP compatibility", COMPATIBILITY_FIELDS)
        adapter, status, reason = entry["adapter"], entry["status"], entry["reason"]
        if adapter not in ADAPTERS:
            raise ValueError(f"unknown MCP adapter {adapter!r}")
        if (status == "supported" and reason != "") or (
            status == "unsupported" and not reason
        ):
            raise ValueError(f"inconsistent MCP support reason for {adapter!r}")
        if status not in {"supported", "unsupported"}:
            raise ValueError(f"invalid MCP support status for {adapter!r}")
    _sorted_unique([entry["adapter"] for entry in entries], "MCP adapters")


def _validate_evidence(evidence: Any) -> None:
    _object(evidence, "MCP evidence", EVIDENCE_FIELDS)
    _https_url(evidence["url"], "MCP evidence")
    try:
        parsed = date.fromisoformat(evidence["verified_on"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid MCP evidence date") from exc
    if parsed.isoformat() != evidence["verified_on"]:
        raise ValueError("MCP evidence date must be canonical")


def _object(
    value: Any,
    label: str,
    required: set[str],
    allowed: set[str] | None = None,
) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    allowed = allowed or required
    if set(value) != required and (not required.issubset(value) or not set(value) <= allowed):
        raise ValueError(f"{label} has missing or unknown fields")


def _https_url(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise ValueError(f"{label} must be an absolute HTTPS URL")


def _sorted_unique(values: list[str], label: str) -> None:
    if values != sorted(set(values)):
        raise ValueError(f"{label} must be sorted and unique")


def _non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item for item in value
    )
