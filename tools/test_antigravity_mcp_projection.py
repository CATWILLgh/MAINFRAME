#!/usr/bin/env python3
"""Tests for the Antigravity MCP projection dialect."""

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
        "id": "antigravity-2.mcp.context7",
        "codec": "antigravity-global-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {
            "root": "antigravity-config",
            "path": "mcp_config.json",
        },
        "map_pointer": "/mcpServers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "antigravity-data",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }


def _assert_rejected(projection):
    try:
        release_mcp_projection.validate_manifest_projections(
            "antigravity-2",
            [projection],
            parse_location=release_contract._location,
        )
    except ValueError:
        return
    raise AssertionError("invalid Antigravity projection was accepted")


def test_antigravity_projection_is_exact_and_uses_server_url():
    projection = _projection()
    release_mcp_projection.validate_manifest_projections(
        "antigravity-2",
        [projection],
        parse_location=release_contract._location,
    )
    assert release_mcp_projection.desired_entry(
        projection, "antigravity-2", _catalog()
    ) == {"serverUrl": "https://mcp.context7.com/mcp"}

    for path, value in (
        (("codec",), "claude-user-http-v1"),
        (("target", "root"), "antigravity-data"),
        (("target", "path"), "settings.json"),
        (("map_pointer",), "/mcp"),
        (("registry", "target", "root"), "antigravity-config"),
        (("registry", "target", "path"), "mcp-ownership.json"),
    ):
        invalid = copy.deepcopy(projection)
        target = invalid
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        _assert_rejected(invalid)


def test_codec_endpoint_keys_are_explicit_and_dialect_specific():
    endpoint_keys = {
        identity: contract["endpoint_key"]
        for identity, contract in release_mcp_projection.CODEC_CONTRACTS.items()
    }
    assert endpoint_keys == {
        ("antigravity-2", "antigravity-global-http-v1"): "serverUrl",
        ("claude-code", "claude-user-http-v1"): "url",
        ("codex", "codex-user-http-v1"): "url",
        ("opencode", "opencode-remote-v1"): "url",
    }


def test_antigravity_keyed_profile_remains_unsupported():
    projection = _projection()
    projection["profile"] = "remote-api-key"
    try:
        release_mcp_projection.desired_entry(
            projection, "antigravity-2", _catalog()
        )
    except ValueError as error:
        assert "incompatible" in str(error)
    else:
        raise AssertionError("keyed Antigravity profile was accepted")


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
