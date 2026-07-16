#!/usr/bin/env python3
"""Hermetic contract tests for the Antigravity immutable release bundle."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import release_contract


def _load_builder():
    source = REPO / "adapters/antigravity-2/build_bundle.py"
    spec = importlib.util.spec_from_file_location(
        "mainframe_antigravity_bundle_test", source
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load bundle builder: {source}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(source.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_bundle_is_self_contained_and_models_external_validation():
    output = Path(tempfile.mkdtemp()) / "bundle"
    _load_builder().build(REPO, output)

    manifest = release_contract.validate_bundle(output)
    assert manifest["component"] == "antigravity-2"
    assert manifest["dependencies"] == ["credential-tools", "mainframe-cli"]
    assert manifest["install_units"] == [
        {
            "id": "antigravity-2.plugin",
            "kind": "tree",
            "source": "plugin",
            "target": {
                "root": "antigravity-config",
                "path": "plugins/mainframe",
            },
            "legacy_source_suffixes": ["dist/antigravity-2/plugin"],
        }
    ]
    resources = {resource["id"]: resource for resource in manifest["resources"]}
    assert resources == {
        "antigravity-2.credentials-index": {
            "id": "antigravity-2.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "antigravity-data",
                "path": "credentials-index.md",
            },
            "observation": "supported",
            "apply": "unimplemented",
        },
        "antigravity-2.live-activation": {
            "id": "antigravity-2.live-activation",
            "strategy": "manual-action",
            "target": {
                "root": "antigravity-config",
                "path": "plugins/mainframe",
            },
            "observation": "unimplemented",
            "apply": "unimplemented",
        },
    }
    credentials = (output / "credentials-index.md").read_text()
    assert "~/.gemini/antigravity/credentials-index.md" in credentials
    assert "{{mainframe.config_root}}" not in credentials
    assert "~/.claude" not in credentials
    assert (output / "plugin/plugin.json").is_file()
    assert not any(
        unit["target"]["root"] == "antigravity-data"
        for unit in manifest["install_units"]
    )


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
