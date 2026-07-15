#!/usr/bin/env python3
"""Dependency graph validation for release manifests."""

from __future__ import annotations

from typing import Any


def reject_dependency_cycles(manifests: list[dict[str, Any]]) -> None:
    dependencies = {
        manifest["component"]: manifest["dependencies"]
        for manifest in manifests
    }
    states: dict[str, str] = {}

    def visit(component: str) -> None:
        if states.get(component) == "visiting":
            raise ValueError(f"dependency cycle includes component {component!r}")
        if states.get(component) == "visited":
            return
        states[component] = "visiting"
        for dependency in dependencies[component]:
            visit(dependency)
        states[component] = "visited"

    for component in sorted(dependencies):
        visit(component)
