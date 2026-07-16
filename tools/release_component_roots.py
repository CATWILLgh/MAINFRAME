#!/usr/bin/env python3
"""Component ownership rules for release bundle target roots."""
from __future__ import annotations

from typing import Any


COMPONENT_ROOTS = {
    "antigravity-2": frozenset({"antigravity-config", "antigravity-data"}),
    "claude-code": frozenset({"claude-config"}),
    "codex": frozenset({"codex-config"}),
    "credential-tools": frozenset({"credentials-config", "home", "user-bin"}),
    "mainframe-cli": frozenset({"user-bin"}),
    "opencode": frozenset({"opencode-config"}),
}
COMPONENT_ROOT_PATHS = {
    ("credential-tools", "home"): frozenset({".bashrc", ".profile", ".zshenv"}),
}
COMPONENT_DEPENDENCIES = {
    "antigravity-2": frozenset({"credential-tools", "mainframe-cli"}),
    "claude-code": frozenset({"credential-tools", "mainframe-cli"}),
    "codex": frozenset({"credential-tools", "mainframe-cli"}),
    "credential-tools": frozenset(),
    "mainframe-cli": frozenset(),
    "opencode": frozenset({"credential-tools", "mainframe-cli"}),
}


def validate_component_targets(component: str, manifest: dict[str, Any]) -> None:
    allowed = COMPONENT_ROOTS.get(component)
    if allowed is None:
        raise ValueError(f"unknown release component {component!r}")
    for collection in ("install_units", "legacy_artifacts", "resources"):
        for record in manifest[collection]:
            target = record["target"]
            root = target["root"]
            if root not in allowed:
                raise ValueError(
                    f"component {component!r} cannot target root {root!r} "
                    f"from {collection}"
                )
            allowed_paths = COMPONENT_ROOT_PATHS.get((component, root))
            if allowed_paths is not None and target["path"] not in allowed_paths:
                raise ValueError(
                    f"component {component!r} cannot target path "
                    f"{target['path']!r} under root {root!r} from {collection}"
                )


def validate_component_dependency(component: str, dependency: str) -> None:
    allowed = COMPONENT_DEPENDENCIES.get(component)
    if allowed is None:
        raise ValueError(f"unknown release component {component!r}")
    if dependency not in allowed:
        raise ValueError(
            f"component {component!r} cannot depend on {dependency!r}"
        )
