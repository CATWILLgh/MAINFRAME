#!/usr/bin/env python3
"""Hermetic component-to-root ownership tests for release bundles."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import release_contract


ALLOWED_ROOTS = {
    "antigravity-2": ("antigravity-config", "antigravity-data"),
    "claude-code": ("claude-config",),
    "codex": ("codex-config",),
    "credential-tools": ("credentials-config", "home", "user-bin"),
    "mainframe-cli": ("user-bin",),
    "opencode": ("opencode-config",),
}


def _manifest(component: str, root: str) -> None:
    bundle = Path(tempfile.mkdtemp())
    (bundle / "payload").write_text("payload\n")
    paths = (
        (".bashrc", ".profile", ".zshenv")
        if root == "home"
        else ("payload", "legacy", "directory")
    )
    release_contract.write_bundle_manifest(
        bundle,
        component=component,
        dependencies=[],
        install_units=[{
            "id": f"{component}.payload",
            "kind": "file",
            "source": "payload",
            "target": {"root": root, "path": paths[0]},
        }],
        legacy_artifacts=[{
            "target": {"root": root, "path": paths[1]},
            "target_suffixes": ["export/legacy"],
        }],
        resources=[{
            "id": f"{component}.directory",
            "strategy": "ensure-directory",
            "target": {"root": root, "path": paths[2]},
            "observation": "supported",
            "apply": "unimplemented",
        }],
    )


def test_component_root_allowlist_accepts_every_declared_pair():
    for component, roots in ALLOWED_ROOTS.items():
        for root in roots:
            _manifest(component, root)


def test_component_root_allowlist_rejects_unknown_root_in_every_collection():
    foreign_root = "unknown-root"
    records = (
        ("install_units", [{
            "id": "codex.payload", "kind": "file", "source": "payload",
            "target": {"root": foreign_root, "path": "payload"},
        }]),
        ("legacy_artifacts", [{
            "target": {"root": foreign_root, "path": "legacy"},
            "target_suffixes": ["export/legacy"],
        }]),
        ("resources", [{
            "id": "codex.directory", "strategy": "ensure-directory",
            "target": {"root": foreign_root, "path": "directory"},
            "observation": "supported", "apply": "unimplemented",
        }]),
    )
    for collection, value in records:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "payload").write_text("payload\n")
        arguments = {"install_units": [], "legacy_artifacts": [], "resources": []}
        arguments[collection] = value
        try:
            release_contract.write_bundle_manifest(
                bundle, component="codex", dependencies=[], **arguments
            )
        except ValueError as exc:
            assert "codex" in str(exc) and foreign_root in str(exc)
        else:
            raise AssertionError(f"foreign root in {collection} was accepted")


def test_component_root_allowlist_rejects_unknown_component_without_targets():
    try:
        release_contract.write_bundle_manifest(
            Path(tempfile.mkdtemp()),
            component="unknown",
            dependencies=[],
            install_units=[],
            resources=[],
        )
    except ValueError as exc:
        assert "unknown release component" in str(exc)
    else:
        raise AssertionError("unknown component without targets was accepted")


def test_credential_tools_home_root_rejects_runtime_paths():
    try:
        bundle = Path(tempfile.mkdtemp())
        (bundle / "payload").write_text("payload\n")
        release_contract.write_bundle_manifest(
            bundle,
            component="credential-tools",
            dependencies=[],
            install_units=[{
                "id": "credential-tools.payload",
                "kind": "file",
                "source": "payload",
                "target": {"root": "home", "path": ".claude/settings.json"},
            }],
            resources=[],
        )
    except ValueError as exc:
        assert ".claude/settings.json" in str(exc)
    else:
        raise AssertionError("credential-tools home escape was accepted")


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
