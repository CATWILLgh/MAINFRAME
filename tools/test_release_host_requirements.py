#!/usr/bin/env python3
"""Hermetic contract tests for native-host release requirements."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract
from release_contract_fields import HOST_REQUIREMENTS_SCHEMA_VERSION


REQUIREMENT = {
    "kind": "darwin-application-bundle-v1",
    "bundle_identifier": "com.google.antigravity",
    "exact_versions": ["2.2.1"],
}


def _write_bundle(*, schema_version: int, requirements=None):
    bundle = Path(tempfile.mkdtemp())
    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="antigravity-2",
        dependencies=[],
        install_units=[],
        resources=[],
        schema_version=schema_version,
        host_requirements=requirements,
    )
    return bundle, manifest


def _assert_invalid(bundle: Path, document: dict) -> None:
    (bundle / "bundle.json").write_text(json.dumps(document, indent=2) + "\n")
    try:
        release_contract.validate_bundle(bundle)
    except ValueError:
        return
    raise AssertionError(f"invalid host requirement was accepted: {document}")


def test_schema_three_writes_and_validates_canonical_requirements():
    bundle, manifest = _write_bundle(
        schema_version=HOST_REQUIREMENTS_SCHEMA_VERSION,
        requirements=[REQUIREMENT],
    )

    assert manifest["schema_version"] == HOST_REQUIREMENTS_SCHEMA_VERSION
    assert manifest["host_requirements"] == [REQUIREMENT]
    assert release_contract.validate_bundle(bundle)["host_requirements"] == [REQUIREMENT]

    second = {**REQUIREMENT, "bundle_identifier": "com.example.second"}
    multiple, multiple_manifest = _write_bundle(
        schema_version=HOST_REQUIREMENTS_SCHEMA_VERSION,
        requirements=[REQUIREMENT, second],
    )
    assert multiple_manifest["host_requirements"] == [second, REQUIREMENT]
    assert release_contract.validate_bundle(multiple)["host_requirements"] == [
        second,
        REQUIREMENT,
    ]

    try:
        _write_bundle(schema_version=HOST_REQUIREMENTS_SCHEMA_VERSION)
    except ValueError as exc:
        assert "host requirements" in str(exc)
    else:
        raise AssertionError("schema version 3 writer accepted no host requirements")


def test_schema_three_rejects_noncanonical_requirements():
    bundle, manifest = _write_bundle(
        schema_version=HOST_REQUIREMENTS_SCHEMA_VERSION,
        requirements=[REQUIREMENT],
    )
    second = {**REQUIREMENT, "bundle_identifier": "com.example.second"}
    invalid_requirements = [
        None,
        {},
        [],
        [{**REQUIREMENT, "kind": "unknown-host"}],
        [{**REQUIREMENT, "unexpected": True}],
        [{**REQUIREMENT, "bundle_identifier": ""}],
        [{**REQUIREMENT, "exact_versions": []}],
        [{**REQUIREMENT, "exact_versions": [""]}],
        [{**REQUIREMENT, "exact_versions": ["2.2.1", "2.2.1"]}],
        [{**REQUIREMENT, "exact_versions": ["2.3.0", "2.2.1"]}],
        [REQUIREMENT, REQUIREMENT],
        [REQUIREMENT, second],
    ]
    for requirements in invalid_requirements:
        _assert_invalid(bundle, {**manifest, "host_requirements": requirements})
    _assert_invalid(
        bundle,
        {key: value for key, value in manifest.items() if key != "host_requirements"},
    )


def test_schema_two_forbids_host_requirements():
    bundle, manifest = _write_bundle(schema_version=2)
    assert "host_requirements" not in manifest
    _assert_invalid(bundle, {**manifest, "host_requirements": []})
    try:
        _write_bundle(schema_version=2, requirements=[REQUIREMENT])
    except ValueError as exc:
        assert "schema version 3 through 5" in str(exc)
    else:
        raise AssertionError("schema version 2 writer accepted host requirements")


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
