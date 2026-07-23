#!/usr/bin/env python3
"""Tier-1 release contracts for optional install features."""

import tempfile
from pathlib import Path

import release_contract


def test_install_unit_feature_is_v5_only_and_strict() -> None:
    bundle = Path(tempfile.mkdtemp())
    (bundle / "feedback").write_text("feedback\n")
    unit = {
        "id": "credential-tools.feedback",
        "kind": "file",
        "source": "feedback",
        "target": {"root": "credentials-config", "path": "feedback"},
        "feature": "dev.harness-feedback",
    }

    manifest = release_contract.write_bundle_manifest(
        bundle,
        component="credential-tools",
        dependencies=[],
        install_units=[unit],
        resources=[],
    )
    assert manifest["schema_version"] == 5
    assert manifest["install_units"][0]["feature"] == "dev.harness-feedback"

    for schema_version, feature in (
        (4, "dev.harness-feedback"),
        (5, "Invalid"),
        (5, None),
    ):
        candidate = dict(unit, feature=feature)
        try:
            release_contract.write_bundle_manifest(
                bundle,
                component="credential-tools",
                dependencies=[],
                install_units=[candidate],
                resources=[],
                schema_version=schema_version,
            )
        except ValueError:
            continue
        raise AssertionError(
            f"schema {schema_version} accepted feature {feature!r}"
        )


if __name__ == "__main__":
    test_install_unit_feature_is_v5_only_and_strict()
    print("1/1 passed")
