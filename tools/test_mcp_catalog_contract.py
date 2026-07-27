#!/usr/bin/env python3
"""Tests for the release-owned MCP catalog contract."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import mcp_catalog_contract


def _catalog():
    return json.loads((REPO / "internal/mcpcatalog/catalog.json").read_text())


def test_source_catalog_is_valid_and_supports_antigravity_standard_storage():
    catalog = _catalog()
    mcp_catalog_contract.validate_catalog(catalog)

    keyed = catalog["servers"][0]["profiles"][0]
    antigravity = keyed["compatibility"][0]
    assert antigravity == {
        "adapter": "antigravity-2",
        "status": "supported",
        "reason": "",
    }


def test_catalog_rejects_unknown_and_incoherent_fields():
    mutations = []
    unknown = _catalog()
    unknown["unknown"] = True
    mutations.append(unknown)

    insecure = _catalog()
    insecure["servers"][0]["profiles"][0]["endpoint"] = "http://example.test/mcp"
    mutations.append(insecure)

    keyless_secret = _catalog()
    authentication = keyless_secret["servers"][0]["profiles"][1]["authentication"]
    authentication["environment_variable"] = "SHOULD_NOT_EXIST"
    mutations.append(keyless_secret)

    mismatched_repository = _catalog()
    mismatched_repository["servers"][0]["repository"]["url"] = (
        "https://github.com/upstash/another-project"
    )
    mutations.append(mismatched_repository)

    non_string_profile = _catalog()
    non_string_profile["servers"][0]["profiles"][0]["name"] = 1
    mutations.append(non_string_profile)

    unsorted = copy.deepcopy(_catalog())
    unsorted["servers"][0]["profiles"].reverse()
    mutations.append(unsorted)

    for catalog in mutations:
        try:
            mcp_catalog_contract.validate_catalog(catalog)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid MCP catalog was accepted")


def test_catalog_entry_requires_reserved_release_location():
    root = Path(tempfile.mkdtemp())
    wrong_path = root / "bundles/claude-code/mcp-catalog.json"
    wrong_path.parent.mkdir(parents=True)
    wrong_path.write_bytes((REPO / "internal/mcpcatalog/catalog.json").read_bytes())
    try:
        mcp_catalog_contract.catalog_entry(root, wrong_path)
    except ValueError as exc:
        assert "reserved" in str(exc)
    else:
        raise AssertionError("bundle-owned MCP catalog path was accepted")


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
