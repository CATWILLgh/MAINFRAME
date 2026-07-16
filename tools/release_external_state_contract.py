#!/usr/bin/env python3
"""Cross-record validation for external-state release resources."""
from __future__ import annotations

from typing import Any


def validate_external_state_units(manifest: dict[str, Any]) -> None:
    units = {
        (
            unit["source"],
            unit["target"]["root"],
            unit["target"]["path"],
        )
        for unit in manifest["install_units"]
        if unit["kind"] == "file"
    }
    for resource in manifest["resources"]:
        if "external_state" not in resource:
            continue
        identity = (
            resource["source"],
            resource["target"]["root"],
            resource["target"]["path"],
        )
        if identity not in units:
            raise ValueError(
                f"resource {resource['id']!r} external state does not match an install unit"
            )
