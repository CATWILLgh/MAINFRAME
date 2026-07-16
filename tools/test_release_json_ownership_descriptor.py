#!/usr/bin/env python3
"""Hermetic tests for versioned JSON map ownership descriptors."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract


def _ownership(
    *,
    map_pointer: object = "/owned",
    registry_root: object = "codex-config",
    registry_path: object = "config.json.mainframe-owned.json",
    schema_version: object = 1,
    entries_pointer: object = "/actions",
) -> dict:
    return {
        "kind": "json-map-entry-registry-v1",
        "map_pointer": map_pointer,
        "entry_schema": "decision-rule-v1",
        "registry": {
            "target": {"root": registry_root, "path": registry_path},
            "schema_version": schema_version,
            "entries_pointer": entries_pointer,
        },
    }


def _resource(
    *,
    strategy: str = "json-key-merge",
    observation: str = "supported",
    ownership: object = None,
    owned_pointers: object = None,
) -> dict:
    resource = {
        "id": "alpha.configuration",
        "strategy": strategy,
        "source": "config.json",
        "target": {"root": "codex-config", "path": "config.json"},
        "observation": observation,
        "apply": "unimplemented",
        "ownership": ownership if ownership is not None else _ownership(),
    }
    if owned_pointers is not None:
        resource["owned_json_pointers"] = owned_pointers
    return resource


def _write(payload: str, resource: dict) -> dict:
    bundle = Path(tempfile.mkdtemp())
    (bundle / "config.json").write_text(payload)
    return release_contract.write_bundle_manifest(
        bundle,
        component="codex",
        dependencies=[],
        install_units=[],
        resources=[resource],
    )


def _assert_rejected(payload: str, resource: dict) -> None:
    try:
        _write(payload, resource)
    except ValueError as exc:
        assert "ownership" in str(exc)
    else:
        raise AssertionError(f"invalid ownership descriptor was accepted: {resource!r}")


def test_json_map_ownership_accepts_strict_versioned_descriptor():
    ownership = _ownership()
    manifest = _write('{"owned":{"action":"deny"}}\n', _resource())
    assert manifest["resources"][0]["ownership"] == ownership


def test_json_map_ownership_requires_exact_shape_and_version():
    valid = _ownership()
    invalid = [
        "registry",
        {},
        {**valid, "unknown": True},
        *[
            {key: value for key, value in valid.items() if key != missing}
            for missing in ("kind", "entry_schema", "registry")
        ],
        {**valid, "kind": "json-map-entry-registry-v2"},
        {**valid, "entry_schema": "unknown"},
        {**valid, "map_pointer": 1},
        {**valid, "map_pointer": ""},
        {**valid, "map_pointer": "/bad~2escape"},
        {**valid, "registry": []},
        {**valid, "registry": {**valid["registry"], "unknown": True}},
        *[
            {
                **valid,
                "registry": {
                    key: value
                    for key, value in valid["registry"].items()
                    if key != missing
                },
            }
            for missing in ("target", "schema_version", "entries_pointer")
        ],
        {
            **valid,
            "registry": {**valid["registry"], "schema_version": True},
        },
        {
            **valid,
            "registry": {**valid["registry"], "schema_version": 2},
        },
        {
            **valid,
            "registry": {**valid["registry"], "entries_pointer": ""},
        },
        {
            **valid,
            "registry": {**valid["registry"], "entries_pointer": "/other"},
        },
    ]
    for ownership in invalid:
        _assert_rejected('{"owned":{}}\n', _resource(ownership=ownership))


def test_json_map_ownership_requires_supported_json_map_source():
    cases = [
        _resource(observation="unimplemented"),
        _resource(strategy="seed-if-absent"),
        _resource(owned_pointers=["/owned"]),
    ]
    for resource in cases:
        _assert_rejected('{"owned":{}}\n', resource)


def test_json_map_ownership_requires_object_source_and_adapter_local_registry():
    cases = [
        ('{"peer":{}}\n', _ownership()),
        ('{"owned":true}\n', _ownership()),
        ('{"owned":{"action":"unknown"}}\n', _ownership()),
        ('{"owned":{"action":{}}}\n', _ownership()),
        ('{"owned":{"action":{"":"deny"}}}\n', _ownership()),
        ('{"owned":{"action":{"pattern":true}}}\n', _ownership()),
        ('{"owned":{}}\n', _ownership(registry_root="opencode-config")),
        ('{"owned":{}}\n', _ownership(registry_path="../registry.json")),
    ]
    for payload, ownership in cases:
        _assert_rejected(payload, _resource(ownership=ownership))


def _run_all():
    tests = [
        function
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    failures = 0
    for function in tests:
        try:
            function()
            print(f"  ok  {function.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {function.__name__}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
