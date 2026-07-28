#!/usr/bin/env python3
"""Focused release-contract tests for managed file ownership."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import release_contract


def test_schema_v6_managed_file_ownership_is_strict_and_collision_checked():
    bundle = Path(tempfile.mkdtemp())
    (bundle / "seed").write_text("")
    ownership = {
        "kind": "managed-file-registry-v1",
        "registry": {
            "target": {
                "root": "credentials-config",
                "path": "mainframe/file-ownership.json",
            },
            "schema_version": 1,
        },
    }
    resource = {
        "id": "credential-tools.secrets-store",
        "strategy": "seed-if-absent",
        "source": "seed",
        "target": {"root": "credentials-config", "path": "secrets.env"},
        "observation": "supported",
        "apply": "supported",
        "file_ownership": ownership,
    }
    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[],
        resources=[resource],
    )
    assert manifest["schema_version"] == 6
    assert manifest["resources"][0]["file_ownership"] == ownership

    for mutate in (
        lambda value: value.update(schema_version=5),
        lambda value: value["resources"][0]["file_ownership"].update(kind="unknown"),
        lambda value: value["resources"][0]["file_ownership"]["registry"].update(
            unexpected=True
        ),
        lambda value: value["resources"][0]["file_ownership"]["registry"][
            "target"
        ].update(path="secrets.env/claims.json"),
    ):
        changed = json.loads(json.dumps(manifest))
        mutate(changed)
        (bundle / "bundle.json").write_text(json.dumps(changed))
        try:
            release_contract.validate_bundle(bundle)
        except ValueError as exc:
            assert "ownership" in str(exc) or "unknown fields" in str(exc)
        else:
            raise AssertionError("invalid managed file ownership was accepted")
    (bundle / "bundle.json").write_text(json.dumps(manifest))


if __name__ == "__main__":
    test_schema_v6_managed_file_ownership_is_strict_and_collision_checked()
    print("1/1 passed")
