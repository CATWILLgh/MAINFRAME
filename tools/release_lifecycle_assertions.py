"""Lifecycle assertions for the packaged MAINFRAME CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ADAPTERS = ("antigravity-2", "claude-code", "codex", "opencode")


def assert_adapter_plans(
    binary: Path,
    output: Path,
    sandbox: Path,
    env: dict[str, str],
) -> None:
    manifests = release_manifests(output)
    for adapter in ADAPTERS:
        operations = run_plan(binary, sandbox, env, [adapter], [])
        assert plan_targets(operations) == expected_targets(manifests, adapter)
        assert all(operation["kind"] == "install" for operation in operations)
        assert_no_internal_fields(operations)


def assert_adapter_lifecycle_plans(
    binary: Path,
    output: Path,
    sandbox: Path,
    env: dict[str, str],
) -> None:
    manifests = release_manifests(output)
    all_installed = observed_components(manifests, set(manifests), "managed_exact")
    for removed in ADAPTERS:
        desired = [adapter for adapter in ADAPTERS if adapter != removed]
        operations = run_plan(binary, sandbox, env, desired, all_installed)
        assert plan_targets(operations) == manifest_targets(manifests, {removed})
        assert all(operation["kind"] == "remove" for operation in operations)
    for adapter in ADAPTERS:
        closure = component_closure(manifests, [adapter])
        previous = observed_components(manifests, closure, "managed_previous")
        operations = run_plan(binary, sandbox, env, [adapter], previous)
        assert plan_targets(operations) == manifest_targets(manifests, closure)
        assert all(operation["kind"] == "replace" for operation in operations)


def run_plan(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
    desired: list[str],
    observed: list[dict],
) -> list[dict]:
    plan = subprocess.run(
        [str(binary), "plan"],
        input=json.dumps(
            {
                "desired": {"components": desired},
                "observed": {"components": observed},
            }
        ),
        text=True,
        capture_output=True,
        cwd=sandbox,
        env=env,
        timeout=30,
    )
    assert plan.returncode == 0, (desired, plan.stdout, plan.stderr)
    return json.loads(plan.stdout)["operations"]


def release_manifests(output: Path) -> dict[str, dict]:
    index = json.loads((output / "release.json").read_text())
    return {
        entry["component"]: json.loads((output / entry["path"]).read_text())
        for entry in index["manifests"]
    }


def expected_targets(manifests: dict[str, dict], selected: str) -> list[tuple]:
    return manifest_targets(manifests, component_closure(manifests, [selected]))


def component_closure(
    manifests: dict[str, dict],
    selected: list[str],
) -> set[str]:
    closure: set[str] = set()
    pending = list(selected)
    while pending:
        component = pending.pop()
        if component in closure:
            continue
        closure.add(component)
        pending.extend(manifests[component]["dependencies"])
    return closure


def manifest_targets(
    manifests: dict[str, dict],
    components: set[str],
) -> list[tuple]:
    return sorted(
        (
            component,
            unit["target"]["root"],
            unit["target"]["path"],
        )
        for component in components
        for unit in manifests[component]["install_units"]
    )


def observed_components(
    manifests: dict[str, dict],
    components: set[str],
    ownership: str,
) -> list[dict]:
    inode = 100
    observed = []
    for component in sorted(components):
        artifacts = []
        for unit in manifests[component]["install_units"]:
            inode += 1
            artifacts.append(
                {
                    "location": unit["target"],
                    "unit_id": unit["id"],
                    "ownership": ownership,
                    "raw_target": f"/releases/old/{component}/{unit['source']}",
                    "link_device": 1,
                    "link_inode": inode,
                }
            )
        observed.append({"id": component, "artifacts": artifacts})
    return observed


def plan_targets(operations: list[dict]) -> list[tuple]:
    return sorted(
        (
            operation["component_id"],
            operation["artifact"]["location"]["root"],
            operation["artifact"]["location"]["path"],
        )
        for operation in operations
    )


def assert_no_internal_fields(operations: list[dict]) -> None:
    encoded = json.dumps(operations)
    for field in ("unit_id", "raw_target", "link_device", "link_inode"):
        assert f'"{field}"' not in encoded
