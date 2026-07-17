#!/usr/bin/env python3
"""Tests for adapter-owned MCP projection descriptors."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import release_contract
import release_mcp_projection


def _catalog():
    return json.loads((REPO / "internal/mcpcatalog/catalog.json").read_text())


def _projection():
    return {
        "id": "opencode.mcp.context7",
        "codec": "opencode-remote-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "opencode-config", "path": "opencode.json"},
        "map_pointer": "/mcp",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "opencode-config",
                "path": "opencode.json.mainframe-mcp.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }


def _claude_projection():
    return {
        "id": "claude-code.mcp.context7",
        "codec": "claude-user-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "home", "path": ".claude.json"},
        "map_pointer": "/mcpServers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "claude-config",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }


def _codex_projection():
    return {
        "id": "codex.mcp.context7",
        "codec": "codex-user-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "codex-config", "path": "config.toml"},
        "map_pointer": "/mcp_servers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "codex-config",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }


def test_projection_is_strict_and_component_local():
    release_mcp_projection.validate_manifest_projections(
        "opencode", [_projection()], parse_location=release_contract._location
    )
    mutations = []
    for path, value in (
        (("unknown",), True),
        (("codec",), "unknown"),
        (("map_pointer",), "/permission"),
        (("target", "root"), "claude-config"),
        (("registry", "entries_pointer"), "/actions"),
        (("registry", "schema_version"), True),
    ):
        projection = copy.deepcopy(_projection())
        target = projection
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        mutations.append(projection)
    for projection in mutations:
        try:
            release_mcp_projection.validate_manifest_projections(
                "opencode", [projection], parse_location=release_contract._location
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid MCP projection was accepted")
    try:
        release_mcp_projection.validate_manifest_projections(
            "codex", [_projection()], parse_location=release_contract._location
        )
    except ValueError:
        pass
    else:
        raise AssertionError("projection crossed its adapter boundary")
    lower = _projection()
    lower["id"] = "a.mcp.context7"
    try:
        release_mcp_projection.validate_manifest_projections(
            "opencode", [_projection(), lower], parse_location=release_contract._location
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unsorted MCP projections were accepted")


def test_desired_entry_is_derived_from_verified_catalog_profile():
    catalog = _catalog()
    catalog["servers"][0]["profiles"][1]["endpoint"] = "https://example.test/mcp"
    assert release_mcp_projection.desired_entry(
        _projection(), "opencode", catalog
    ) == {"type": "remote", "url": "https://example.test/mcp"}
    keyed = _projection()
    keyed["profile"] = "remote-api-key"
    try:
        release_mcp_projection.desired_entry(keyed, "opencode", _catalog())
    except ValueError:
        pass
    else:
        raise AssertionError("keyed profile entered the keyless projection")


def test_claude_projection_is_exact_and_uses_http_dialect():
    projection = _claude_projection()
    release_mcp_projection.validate_manifest_projections(
        "claude-code", [projection], parse_location=release_contract._location
    )
    assert release_mcp_projection.desired_entry(
        projection, "claude-code", _catalog()
    ) == {"type": "http", "url": "https://mcp.context7.com/mcp"}
    mutations = (
        (("codec",), "opencode-remote-v1"),
        (("target", "path"), ".claude/settings.json"),
        (("target", "root"), "claude-config"),
        (("map_pointer",), "/mcp"),
        (("registry", "target", "root"), "home"),
        (("registry", "target", "path"), "mainframe-mcp.json"),
    )
    for path, value in mutations:
        invalid = copy.deepcopy(projection)
        target = invalid
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        try:
            release_mcp_projection.validate_manifest_projections(
                "claude-code", [invalid], parse_location=release_contract._location
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid Claude projection was accepted: {path}")


def test_codex_projection_is_exact_and_uses_toml_http_dialect():
    projection = _codex_projection()
    release_mcp_projection.validate_manifest_projections(
        "codex", [projection], parse_location=release_contract._location
    )
    assert release_mcp_projection.desired_entry(
        projection, "codex", _catalog()
    ) == {"url": "https://mcp.context7.com/mcp"}
    for path, value in (
        (("codec",), "opencode-remote-v1"),
        (("target", "root"), "home"),
        (("target", "path"), "settings.toml"),
        (("map_pointer",), "/mcp"),
        (("registry", "target", "path"), "mcp-ownership.json"),
    ):
        invalid = copy.deepcopy(projection)
        target = invalid
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        try:
            release_mcp_projection.validate_manifest_projections(
                "codex", [invalid], parse_location=release_contract._location
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid Codex projection was accepted: {path}")


def test_release_rejects_duplicate_claim_and_registry_overlap():
    projection = _projection()
    manifest = {
        "component": "opencode",
        "dependencies": [],
        "install_units": [],
        "legacy_artifacts": [],
        "resources": [],
        "mcp_projections": [projection, copy.deepcopy(projection)],
    }
    try:
        release_mcp_projection.validate_release_projections(
            [manifest],
            _catalog(),
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate MCP projection claim was accepted")

    manifest["mcp_projections"] = [projection]
    manifest["resources"] = [{
        "id": "opencode.registry-collision",
        "strategy": "seed-if-absent",
        "target": projection["registry"]["target"],
    }]
    try:
        release_mcp_projection.validate_release_projections(
            [manifest],
            _catalog(),
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("MCP registry overlap was accepted")

    manifest["resources"] = [{
        "id": "opencode.registry-target",
        "strategy": "json-key-merge",
        "target": {"root": "opencode-config", "path": "permissions.json"},
        "ownership": {
            "map_pointer": "/permission",
            "registry": {"target": projection["target"]},
        },
    }]
    try:
        release_mcp_projection.validate_release_projections(
            [manifest],
            _catalog(),
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("MCP target overlapped an ownership registry")


def test_release_allows_distinct_servers_to_share_registry():
    first = _projection()
    second = copy.deepcopy(first)
    second["id"] = "opencode.mcp.docs"
    second["server"] = "docs"
    second["entry_key"] = "docs"
    catalog = _catalog()
    server = copy.deepcopy(catalog["servers"][0])
    server["id"] = "docs"
    server["name"] = "Docs"
    catalog["servers"].append(server)
    manifest = {
        "component": "opencode",
        "dependencies": [],
        "install_units": [],
        "legacy_artifacts": [],
        "resources": [],
        "mcp_projections": [first, second],
    }
    release_mcp_projection.validate_release_projections(
        [manifest],
        catalog,
        parse_location=release_contract._location,
        locations_overlap=release_contract._locations_overlap,
    )


def test_release_rejects_json_and_toml_claims_on_one_target():
    projection = _codex_projection()
    manifest = {
        "component": "codex",
        "dependencies": [],
        "install_units": [],
        "legacy_artifacts": [],
        "resources": [{
            "id": "codex.config-json",
            "strategy": "json-key-merge",
            "target": projection["target"],
            "owned_json_pointers": ["/unrelated"],
        }],
        "mcp_projections": [projection],
    }
    try:
        release_mcp_projection.validate_release_projections(
            [manifest],
            _catalog(),
            parse_location=release_contract._location,
            locations_overlap=release_contract._locations_overlap,
        )
    except ValueError as error:
        assert "format" in str(error)
    else:
        raise AssertionError("mixed JSON and TOML target was accepted")


def _run_all():
    failures = 0
    tests = [
        (name, function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    for name, function in tests:
        try:
            function()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
