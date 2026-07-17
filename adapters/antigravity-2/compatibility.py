#!/usr/bin/env python3
"""Antigravity native-host compatibility policies."""

from release_host_requirements import DARWIN_APPLICATION_BUNDLE_V1

BUNDLE_IDENTIFIER = "com.google.antigravity"
LEGACY_SUPPORTED_MAJOR = "2"
MANAGED_EXACT_VERSIONS = ("2.2.1",)


def managed_host_requirements() -> list[dict[str, object]]:
    return [
        {
            "kind": DARWIN_APPLICATION_BUNDLE_V1,
            "bundle_identifier": BUNDLE_IDENTIFIER,
            "exact_versions": list(MANAGED_EXACT_VERSIONS),
        }
    ]
